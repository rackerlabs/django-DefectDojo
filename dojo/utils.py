from dojo.authorization.roles_permissions import Permissions
from dojo.finding.queries import get_authorized_findings
import re
import binascii
import os
import hashlib
import bleach
import mimetypes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from calendar import monthrange
from datetime import date, datetime
from math import pi, sqrt
import vobject
from dateutil.relativedelta import relativedelta, MO, SU
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.urls import get_resolver, reverse
from django.db.models import Q, Sum, Case, When, IntegerField, Value, Count
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.query import QuerySet
import calendar as tcalendar
from dojo.github import add_external_issue_github, update_external_issue_github, close_external_issue_github, reopen_external_issue_github
from dojo.models import Finding, Engagement, Finding_Group, Finding_Template, Product, \
    Dojo_User, Test, User, System_Settings, Notifications, Endpoint, Benchmark_Type, \
    Language_Type, Languages, Rule
from asteval import Interpreter
from dojo.notifications.helper import create_notification
import logging
import itertools
from django.contrib import messages
from django.http import HttpResponseRedirect
import crum
from dojo.celery import app
from dojo.decorators import dojo_async_task, dojo_model_from_id, dojo_model_to_id


logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


"""
Helper functions for DefectDojo
"""


def do_false_positive_history(new_finding, *args, **kwargs):
    logger.debug('%s: sync false positive history', new_finding.id)
    if new_finding.endpoints.count() == 0:
        # if no endpoints on new finding, then look at cwe + test_type + hash_code. or title + test_type + hash_code
        eng_findings_cwe = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            cwe=new_finding.cwe,
            test__test_type=new_finding.test.test_type,
            false_p=True, hash_code=new_finding.hash_code).exclude(id=new_finding.id).exclude(cwe=None).values('id')
        eng_findings_title = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            title=new_finding.title,
            test__test_type=new_finding.test.test_type,
            false_p=True, hash_code=new_finding.hash_code).exclude(id=new_finding.id).values('id')
        total_findings = eng_findings_cwe | eng_findings_title
    else:
        # if endpoints on new finding, then look at ONLY cwe + test_type. or title + test_type (hash_code doesn't matter!)
        eng_findings_cwe = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            cwe=new_finding.cwe,
            test__test_type=new_finding.test.test_type,
            false_p=True).exclude(id=new_finding.id).exclude(cwe=None).exclude(endpoints=None).values('id')
        eng_findings_title = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            title=new_finding.title,
            test__test_type=new_finding.test.test_type,
            false_p=True).exclude(id=new_finding.id).exclude(endpoints=None).values('id')

    total_findings = eng_findings_cwe | eng_findings_title

    deduplicationLogger.debug("cwe   query: %s", eng_findings_cwe.query)
    deduplicationLogger.debug("title query: %s", eng_findings_title.query)

    # TODO this code retrieves all matching findings + data. in 3 queries. just to check if there is a non-zero amount of matching findings.
    # if we keep false positive history like this, this can be rewritten into 1 query that performs these counts.

    deduplicationLogger.debug("False positive history: Found " +
        str(len(eng_findings_cwe)) + " findings with same cwe, " +
        str(len(eng_findings_title)) + " findings with same title: " +
        str(len(total_findings)) + " findings with either same title or same cwe")

    if total_findings.count() > 0:
        new_finding.false_p = True
        new_finding.active = False
        new_finding.verified = True
        super(Finding, new_finding).save(*args, **kwargs)


# true if both findings are on an engagement that have a different "deduplication on engagement" configuration
def is_deduplication_on_engagement_mismatch(new_finding, to_duplicate_finding):
    return not new_finding.test.engagement.deduplication_on_engagement and to_duplicate_finding.test.engagement.deduplication_on_engagement


@dojo_model_to_id
@dojo_async_task
@app.task
@dojo_model_from_id
def do_dedupe_finding_task(new_finding, *args, **kwargs):
    return do_dedupe_finding(new_finding, *args, **kwargs)


def do_dedupe_finding(new_finding, *args, **kwargs):
    try:
        enabled = System_Settings.objects.get(no_cache=True).enable_deduplication
    except System_Settings.DoesNotExist:
        logger.warning("system settings not found")
        enabled = False
    if enabled:
        deduplicationLogger.debug('dedupe for: ' + str(new_finding.id) +
                    ":" + str(new_finding.title))
        # TODO use test.dedupe_algo and case statement
        if hasattr(settings, 'DEDUPLICATION_ALGORITHM_PER_PARSER'):
            scan_type = new_finding.test.test_type.name
            deduplicationLogger.debug('scan_type for this finding is :' + scan_type)
            # Default algorithm
            deduplicationAlgorithm = settings.DEDUPE_ALGO_LEGACY
            # Check for an override for this scan_type in the deduplication configuration
            if (scan_type in settings.DEDUPLICATION_ALGORITHM_PER_PARSER):
                deduplicationAlgorithm = settings.DEDUPLICATION_ALGORITHM_PER_PARSER[scan_type]
            deduplicationLogger.debug('deduplication algorithm: ' + deduplicationAlgorithm)
            if(deduplicationAlgorithm == settings.DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL):
                deduplicate_unique_id_from_tool(new_finding)
            elif(deduplicationAlgorithm == settings.DEDUPE_ALGO_HASH_CODE):
                deduplicate_hash_code(new_finding)
            elif(deduplicationAlgorithm == settings.DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL_OR_HASH_CODE):
                deduplicate_uid_or_hash_code(new_finding)
            else:
                logger.debug('dedupe legacy start')
                deduplicate_legacy(new_finding)
                logger.debug('dedupe legacy start.done.')
        else:
            deduplicationLogger.debug("no configuration per parser found; using legacy algorithm")
            deduplicate_legacy(new_finding)
    else:
        deduplicationLogger.debug("dedupe: skipping dedupe because it's disabled in system settings get()")


def deduplicate_legacy(new_finding):
    # ---------------------------------------------------------
    # 1) Collects all the findings that have the same:
    #      (title  and static_finding and dynamic_finding)
    #      or (CWE and static_finding and dynamic_finding)
    #    as the new one
    #    (this is "cond1")
    # ---------------------------------------------------------
    if new_finding.test.engagement.deduplication_on_engagement:
        eng_findings_cwe = Finding.objects.filter(
            test__engagement=new_finding.test.engagement,
            cwe=new_finding.cwe).exclude(id=new_finding.id).exclude(cwe=0).exclude(duplicate=True).values('id')
        eng_findings_title = Finding.objects.filter(
            test__engagement=new_finding.test.engagement,
            title=new_finding.title).exclude(id=new_finding.id).exclude(duplicate=True).values('id')
    else:
        eng_findings_cwe = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            cwe=new_finding.cwe).exclude(id=new_finding.id).exclude(cwe=0).exclude(duplicate=True).values('id')
        eng_findings_title = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            title=new_finding.title).exclude(id=new_finding.id).exclude(duplicate=True).values('id')

    total_findings = Finding.objects.filter(Q(id__in=eng_findings_cwe) | Q(id__in=eng_findings_title)).prefetch_related('endpoints', 'test', 'test__engagement', 'found_by', 'original_finding', 'test__test_type')
    deduplicationLogger.debug("Found " +
        str(len(eng_findings_cwe)) + " findings with same cwe, " +
        str(len(eng_findings_title)) + " findings with same title: " +
        str(len(total_findings)) + " findings with either same title or same cwe")

    # total_findings = total_findings.order_by('date')
    for find in total_findings.order_by('id'):
        flag_endpoints = False
        flag_line_path = False
        flag_hash = False
        if is_deduplication_on_engagement_mismatch(new_finding, find):
            deduplicationLogger.debug(
                'deduplication_on_engagement_mismatch, skipping dedupe.')
            continue

        # ---------------------------------------------------------
        # 2) If existing and new findings have endpoints: compare them all
        #    Else look at line+file_path
        #    (if new finding is not static, do not deduplicate)
        # ---------------------------------------------------------

        if find.endpoints.count() != 0 and new_finding.endpoints.count() != 0:
            list1 = [str(e) for e in new_finding.endpoints.all()]
            list2 = [str(e) for e in find.endpoints.all()]

            if all(x in list1 for x in list2):
                deduplicationLogger.debug("%s: existing endpoints are present in new finding", find.id)
                flag_endpoints = True
        elif new_finding.static_finding and new_finding.file_path and len(new_finding.file_path) > 0:
            if str(find.line) == str(new_finding.line) and find.file_path == new_finding.file_path:
                deduplicationLogger.debug("%s: file_path and line match", find.id)
                flag_line_path = True
            else:
                deduplicationLogger.debug("no endpoints on one of the findings and file_path doesn't match; Deduplication will not occur")
        else:
            deduplicationLogger.debug('find.static/dynamic: %s/%s', find.static_finding, find.dynamic_finding)
            deduplicationLogger.debug('new_finding.static/dynamic: %s/%s', new_finding.static_finding, new_finding.dynamic_finding)
            deduplicationLogger.debug('find.file_path: %s', find.file_path)
            deduplicationLogger.debug('new_finding.file_path: %s', new_finding.file_path)

            deduplicationLogger.debug("no endpoints on one of the findings and the new finding is either dynamic or doesn't have a file_path; Deduplication will not occur")

        if find.hash_code == new_finding.hash_code:
            flag_hash = True

        deduplicationLogger.debug(
            'deduplication flags for new finding (' + ('dynamic' if new_finding.dynamic_finding else 'static') + ') ' + str(new_finding.id) + ' and existing finding ' + str(find.id) +
            ' flag_endpoints: ' + str(flag_endpoints) + ' flag_line_path:' + str(flag_line_path) + ' flag_hash:' + str(flag_hash))

        # ---------------------------------------------------------
        # 3) Findings are duplicate if (cond1 is true) and they have the same:
        #    hash
        #    and (endpoints or (line and file_path)
        # ---------------------------------------------------------
        if ((flag_endpoints or flag_line_path) and flag_hash):
            try:
                set_duplicate(new_finding, find)
            except Exception as e:
                deduplicationLogger.debug(str(e))
                continue

            break


def deduplicate_unique_id_from_tool(new_finding):
    if new_finding.test.engagement.deduplication_on_engagement:
        existing_findings = Finding.objects.filter(
            test__engagement=new_finding.test.engagement,
            unique_id_from_tool=new_finding.unique_id_from_tool).exclude(
                id=new_finding.id).exclude(
                    unique_id_from_tool=None).exclude(
                        duplicate=True).order_by('id')
    else:
        existing_findings = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            # the unique_id_from_tool is unique for a given tool: do not compare with other tools
            test__test_type=new_finding.test.test_type,
            unique_id_from_tool=new_finding.unique_id_from_tool).exclude(
                id=new_finding.id).exclude(
                    unique_id_from_tool=None).exclude(
                        duplicate=True).order_by('id')

    deduplicationLogger.debug("Found " +
        str(len(existing_findings)) + " findings with same unique_id_from_tool")
    for find in existing_findings:
        if is_deduplication_on_engagement_mismatch(new_finding, find):
            deduplicationLogger.debug(
                'deduplication_on_engagement_mismatch, skipping dedupe.')
            continue
        try:
            set_duplicate(new_finding, find)
        except Exception as e:
            deduplicationLogger.debug(str(e))
            continue
        break


def deduplicate_hash_code(new_finding):
    if new_finding.test.engagement.deduplication_on_engagement:
        existing_findings = Finding.objects.filter(
            test__engagement=new_finding.test.engagement,
            hash_code=new_finding.hash_code).exclude(
                id=new_finding.id).exclude(
                    hash_code=None).exclude(
                        duplicate=True).order_by('id')
    else:
        existing_findings = Finding.objects.filter(
            test__engagement__product=new_finding.test.engagement.product,
            hash_code=new_finding.hash_code).exclude(
                id=new_finding.id).exclude(
                    hash_code=None).exclude(
                        duplicate=True).order_by('id')

    deduplicationLogger.debug("Found " +
        str(len(existing_findings)) + " findings with same hash_code")
    for find in existing_findings:
        if is_deduplication_on_engagement_mismatch(new_finding, find):
            deduplicationLogger.debug(
                'deduplication_on_engagement_mismatch, skipping dedupe.')
            continue
        try:
            set_duplicate(new_finding, find)
        except Exception as e:
            deduplicationLogger.debug(str(e))
            continue
        break


def deduplicate_uid_or_hash_code(new_finding):
    if new_finding.test.engagement.deduplication_on_engagement:
        existing_findings = Finding.objects.filter(
            (Q(hash_code__isnull=False) & Q(hash_code=new_finding.hash_code)) |
            # unique_id_from_tool can only apply to the same test_type because it is parser dependent
            (Q(unique_id_from_tool__isnull=False) & Q(unique_id_from_tool=new_finding.unique_id_from_tool) & Q(test__test_type=new_finding.test.test_type)),
            test__engagement=new_finding.test.engagement).exclude(
                id=new_finding.id).exclude(
                        duplicate=True).order_by('id')
    else:
        # same without "test__engagement=new_finding.test.engagement" condition
        existing_findings = Finding.objects.filter(
            (Q(hash_code__isnull=False) & Q(hash_code=new_finding.hash_code)) |
            (Q(unique_id_from_tool__isnull=False) & Q(unique_id_from_tool=new_finding.unique_id_from_tool) & Q(test__test_type=new_finding.test.test_type)),
            test__engagement__product=new_finding.test.engagement.product).exclude(
                id=new_finding.id).exclude(
                        duplicate=True).order_by('id')
    deduplicationLogger.debug("Found " +
        str(len(existing_findings)) + " findings with either the same unique_id_from_tool or hash_code")
    for find in existing_findings:
        if is_deduplication_on_engagement_mismatch(new_finding, find):
            deduplicationLogger.debug(
                'deduplication_on_engagement_mismatch, skipping dedupe.')
            continue
        try:
            set_duplicate(new_finding, find)
        except Exception as e:
            deduplicationLogger.debug(str(e))
            continue
        break


def set_duplicate(new_finding, existing_finding):
    if existing_finding.duplicate:
        logger.debug('existing finding: %s:%s:duplicate=%s;duplicate_finding=%s', existing_finding.id, existing_finding.title, existing_finding.duplicate, existing_finding.duplicate_finding.id if existing_finding.duplicate_finding else 'None')
        raise Exception("Existing finding is a duplicate")
    if existing_finding.id == new_finding.id:
        raise Exception("Can not add duplicate to itself")
    deduplicationLogger.debug('Setting new finding ' + str(new_finding.id) + ' as a duplicate of existing finding ' + str(existing_finding.id))
    if is_duplicate_reopen(new_finding, existing_finding):
        set_duplicate_reopen(new_finding, existing_finding)
    new_finding.duplicate = True
    new_finding.active = False
    new_finding.verified = False
    new_finding.duplicate_finding = existing_finding

    # Make sure transitive duplication is flattened
    # if A -> B and B is made a duplicate of C here, aferwards:
    # A -> C and B -> C should be true
    for find in new_finding.original_finding.all().order_by('-id'):
        new_finding.original_finding.remove(find)
        set_duplicate(find, existing_finding)
    existing_finding.found_by.add(new_finding.test.test_type)
    logger.debug('saving new finding: %d', new_finding.id)
    super(Finding, new_finding).save()
    logger.debug('saving existing finding: %d', existing_finding.id)
    super(Finding, existing_finding).save()


def is_duplicate_reopen(new_finding, existing_finding):
    if (existing_finding.is_mitigated or existing_finding.mitigated) and not existing_finding.out_of_scope and not existing_finding.false_p and new_finding.active and not new_finding.is_mitigated:
        return True
    else:
        return False


def set_duplicate_reopen(new_finding, existing_finding):
    logger.debug('duplicate reopen existing finding')
    existing_finding.mitigated = new_finding.mitigated
    existing_finding.is_mitigated = new_finding.is_mitigated
    existing_finding.active = new_finding.active
    existing_finding.verified = new_finding.verified
    existing_finding.notes.create(author=existing_finding.reporter,
                                    entry="This finding has been automatically re-openend as it was found in recent scans.")
    existing_finding.save()


def do_apply_rules(new_finding, *args, **kwargs):
    rules = Rule.objects.filter(applies_to='Finding', parent_rule=None)
    for rule in rules:
        child_val = True
        child_list = [val for val in rule.child_rules.all()]
        while (len(child_list) != 0):
            child_val = child_val and child_rule(child_list.pop(), new_finding)
        if child_val:
            if rule.operator == 'Matches':
                if getattr(new_finding, rule.match_field) == rule.match_text:
                    if rule.application == 'Append':
                        set_attribute_rule(new_finding, rule, (getattr(
                            new_finding, rule.applied_field) + rule.text))
                    else:
                        set_attribute_rule(new_finding, rule, rule.text)
                        new_finding.save(dedupe_option=False,
                                         rules_option=False)
            else:
                if rule.match_text in getattr(new_finding, rule.match_field):
                    if rule.application == 'Append':
                        set_attribute_rule(new_finding, rule, (getattr(
                            new_finding, rule.applied_field) + rule.text))
                    else:
                        set_attribute_rule(new_finding, rule, rule.text)
                        new_finding.save(dedupe_option=False,
                                         rules_option=False)


def set_attribute_rule(new_finding, rule, value):
    if rule.text == "True":
        setattr(new_finding, rule.applied_field, True)
    elif rule.text == "False":
        setattr(new_finding, rule.applied_field, False)
    else:
        setattr(new_finding, rule.applied_field, value)


def child_rule(rule, new_finding):
    if rule.operator == 'Matches':
        if getattr(new_finding, rule.match_field) == rule.match_text:
            return True
        else:
            return False
    else:
        if rule.match_text in getattr(new_finding, rule.match_field):
            return True
        else:
            return False


def count_findings(findings):
    product_count = {}
    finding_count = {'low': 0, 'med': 0, 'high': 0, 'crit': 0}
    for f in findings:
        product = f.test.engagement.product
        if product in product_count:
            product_count[product][4] += 1
            if f.severity == 'Low':
                product_count[product][3] += 1
                finding_count['low'] += 1
            if f.severity == 'Medium':
                product_count[product][2] += 1
                finding_count['med'] += 1
            if f.severity == 'High':
                product_count[product][1] += 1
                finding_count['high'] += 1
            if f.severity == 'Critical':
                product_count[product][0] += 1
                finding_count['crit'] += 1
        else:
            product_count[product] = [0, 0, 0, 0, 0]
            product_count[product][4] += 1
            if f.severity == 'Low':
                product_count[product][3] += 1
                finding_count['low'] += 1
            if f.severity == 'Medium':
                product_count[product][2] += 1
                finding_count['med'] += 1
            if f.severity == 'High':
                product_count[product][1] += 1
                finding_count['high'] += 1
            if f.severity == 'Critical':
                product_count[product][0] += 1
                finding_count['crit'] += 1
    return product_count, finding_count


def findings_this_period(findings, period_type, stuff, o_stuff, a_stuff):
    # periodType: 0 - weeks
    # 1 - months
    now = timezone.now()
    for i in range(6):
        counts = []
        # Weeks start on Monday
        if period_type == 0:
            curr = now - relativedelta(weeks=i)
            start_of_period = curr - relativedelta(
                weeks=1, weekday=0, hour=0, minute=0, second=0)
            end_of_period = curr + relativedelta(
                weeks=0, weekday=0, hour=0, minute=0, second=0)
        else:
            curr = now - relativedelta(months=i)
            start_of_period = curr - relativedelta(
                day=1, hour=0, minute=0, second=0)
            end_of_period = curr + relativedelta(
                day=31, hour=23, minute=59, second=59)

        o_count = {
            'closed': 0,
            'zero': 0,
            'one': 0,
            'two': 0,
            'three': 0,
            'total': 0
        }
        a_count = {
            'closed': 0,
            'zero': 0,
            'one': 0,
            'two': 0,
            'three': 0,
            'total': 0
        }
        for f in findings:
            if f.mitigated is not None and end_of_period >= f.mitigated >= start_of_period:
                o_count['closed'] += 1
            elif f.mitigated is not None and f.mitigated > end_of_period and f.date <= end_of_period.date():
                if f.severity == 'Critical':
                    o_count['zero'] += 1
                elif f.severity == 'High':
                    o_count['one'] += 1
                elif f.severity == 'Medium':
                    o_count['two'] += 1
                elif f.severity == 'Low':
                    o_count['three'] += 1
            elif f.mitigated is None and f.date <= end_of_period.date():
                if f.severity == 'Critical':
                    o_count['zero'] += 1
                    a_count['zero'] += 1
                elif f.severity == 'High':
                    o_count['one'] += 1
                    a_count['one'] += 1
                elif f.severity == 'Medium':
                    o_count['two'] += 1
                    a_count['two'] += 1
                elif f.severity == 'Low':
                    o_count['three'] += 1
                    a_count['three'] += 1

        total = sum(o_count.values()) - o_count['closed']
        if period_type == 0:
            counts.append(
                start_of_period.strftime("%b %d") + " - " +
                end_of_period.strftime("%b %d"))
        else:
            counts.append(start_of_period.strftime("%b %Y"))
        counts.append(o_count['zero'])
        counts.append(o_count['one'])
        counts.append(o_count['two'])
        counts.append(o_count['three'])
        counts.append(total)
        counts.append(o_count['closed'])

        stuff.append(counts)
        o_stuff.append(counts[:-1])

        a_counts = []
        a_total = sum(a_count.values())
        if period_type == 0:
            a_counts.append(
                start_of_period.strftime("%b %d") + " - " +
                end_of_period.strftime("%b %d"))
        else:
            a_counts.append(start_of_period.strftime("%b %Y"))
        a_counts.append(a_count['zero'])
        a_counts.append(a_count['one'])
        a_counts.append(a_count['two'])
        a_counts.append(a_count['three'])
        a_counts.append(a_total)
        a_stuff.append(a_counts)


def add_breadcrumb(parent=None,
                   title=None,
                   top_level=True,
                   url=None,
                   request=None,
                   clear=False):
    title_done = False
    if clear:
        request.session['dojo_breadcrumbs'] = None
        return
    else:
        crumbs = request.session.get('dojo_breadcrumbs', None)

    if top_level or crumbs is None:
        crumbs = [
            {
                'title': 'Home',
                'url': reverse('home')
            },
        ]
        if parent is not None and getattr(parent, "get_breadcrumbs", None):
            crumbs += parent.get_breadcrumbs()
        else:
            title_done = True
            crumbs += [{
                'title': title,
                'url': request.get_full_path() if url is None else url
            }]
    else:
        resolver = get_resolver(None).resolve
        if parent is not None and getattr(parent, "get_breadcrumbs", None):
            obj_crumbs = parent.get_breadcrumbs()
            if title is not None:
                obj_crumbs += [{
                    'title':
                    title,
                    'url':
                    request.get_full_path() if url is None else url
                }]
        else:
            title_done = True
            obj_crumbs = [{
                'title':
                title,
                'url':
                request.get_full_path() if url is None else url
            }]

        for crumb in crumbs:
            crumb_to_resolve = crumb['url'] if '?' not in crumb[
                'url'] else crumb['url'][:crumb['url'].index('?')]
            crumb_view = resolver(crumb_to_resolve)
            for obj_crumb in obj_crumbs:
                obj_crumb_to_resolve = obj_crumb[
                    'url'] if '?' not in obj_crumb['url'] else obj_crumb[
                        'url'][:obj_crumb['url'].index('?')]
                obj_crumb_view = resolver(obj_crumb_to_resolve)

                if crumb_view.view_name == obj_crumb_view.view_name:
                    if crumb_view.kwargs == obj_crumb_view.kwargs:
                        if len(obj_crumbs) == 1 and crumb in crumbs:
                            crumbs = crumbs[:crumbs.index(crumb)]
                        else:
                            obj_crumbs.remove(obj_crumb)
                    else:
                        if crumb in crumbs:
                            crumbs = crumbs[:crumbs.index(crumb)]

        crumbs += obj_crumbs

    request.session['dojo_breadcrumbs'] = crumbs


def is_title_in_breadcrumbs(title):
    request = crum.get_current_request()
    if request is None:
        return False

    breadcrumbs = request.session.get('dojo_breadcrumbs')
    if breadcrumbs is None:
        return False

    for breadcrumb in breadcrumbs:
        if breadcrumb.get('title') == title:
            return True

    return False


def get_punchcard_data(objs, start_date, weeks, view='Finding'):
    # use try catch to make sure any teething bugs in the bunchcard don't break the dashboard
    try:
        # gather findings over past half year, make sure to start on a sunday
        first_sunday = start_date - relativedelta(weekday=SU(-1))
        last_sunday = start_date + relativedelta(weeks=weeks)

        # reminder: The first week of a year is the one that contains the year’s first Thursday
        # so we could have for 29/12/2019: week=1 and year=2019 :-D. So using week number from db is not practical
        if view == 'Finding':
            severities_by_day = objs.filter(created__date__gte=first_sunday).filter(created__date__lt=last_sunday) \
                                        .values('created__date') \
                                        .annotate(count=Count('id')) \
                                        .order_by('created__date')
        elif view == 'Endpoint':
            severities_by_day = objs.filter(date__gte=first_sunday).filter(date__lt=last_sunday) \
                                        .values('date') \
                                        .annotate(count=Count('id')) \
                                        .order_by('date')
        # return empty stuff if no findings to be statted
        if severities_by_day.count() <= 0:
            return None, None

        # day of the week numbers:
        # javascript  database python
        # sun 6         1       6
        # mon 5         2       0
        # tue 4         3       1
        # wed 3         4       2
        # thu 2         5       3
        # fri 1         6       4
        # sat 0         7       5

        # map from python to javascript, do not use week numbers or day numbers from database.
        day_offset = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0, 6: 6}

        punchcard = list()
        ticks = list()
        highest_day_count = 0
        tick = 0
        day_counts = [0, 0, 0, 0, 0, 0, 0]

        start_of_week = timezone.make_aware(datetime.combine(first_sunday, datetime.min.time()))
        start_of_next_week = start_of_week + relativedelta(weeks=1)
        day_counts = [0, 0, 0, 0, 0, 0, 0]

        for day in severities_by_day:
            if view == 'Finding':
                created = day['created__date']
            elif view == 'Endpoint':
                created = day['date']
            day_count = day['count']

            created = timezone.make_aware(datetime.combine(created, datetime.min.time()))

            if created < start_of_week:
                raise ValueError('date found outside supported range: ' + str(created))
            else:
                if created >= start_of_week and created < start_of_next_week:
                    # add day count to current week data
                    day_counts[day_offset[created.weekday()]] = day_count
                    highest_day_count = max(highest_day_count, day_count)
                else:
                    # created >= start_of_next_week, so store current week, prepare for next
                    while created >= start_of_next_week:
                        week_data, label = get_week_data(start_of_week, tick, day_counts)
                        punchcard.extend(week_data)
                        ticks.append(label)
                        tick += 1

                        # new week, new values!
                        day_counts = [0, 0, 0, 0, 0, 0, 0]
                        start_of_week = start_of_next_week
                        start_of_next_week += relativedelta(weeks=1)

                    # finally a day that falls into the week bracket
                    day_counts[day_offset[created.weekday()]] = day_count
                    highest_day_count = max(highest_day_count, day_count)

        # add week in progress + empty weeks on the end if needed
        while tick < weeks + 1:
            # print(tick)
            week_data, label = get_week_data(start_of_week, tick, day_counts)
            # print(week_data, label)
            punchcard.extend(week_data)
            ticks.append(label)
            tick += 1

            day_counts = [0, 0, 0, 0, 0, 0, 0]
            start_of_week = start_of_next_week
            start_of_next_week += relativedelta(weeks=1)

        # adjust the size or circles
        ratio = (sqrt(highest_day_count / pi))
        for punch in punchcard:
            # front-end needs both the count for the label and the ratios of the radii of the circles
            punch.append(punch[2])
            punch[2] = (sqrt(punch[2] / pi)) / ratio

        return punchcard, ticks

    except Exception as e:
        logger.exception('Not showing punchcard graph due to exception gathering data', e)
        return None, None


def get_week_data(week_start_date, tick, day_counts):
    data = []
    for i in range(0, len(day_counts)):
        data.append([tick, i, day_counts[i]])
    label = [tick, week_start_date.strftime("<span class='small'>%m/%d<br/>%Y</span>")]
    return data, label


# 5 params
def get_period_counts_legacy(findings,
                             findings_closed,
                             accepted_findings,
                             period_interval,
                             start_date,
                             relative_delta='months'):
    opened_in_period = list()
    accepted_in_period = list()
    opened_in_period.append(
        ['Timestamp', 'Date', 'S0', 'S1', 'S2', 'S3', 'Total', 'Closed'])
    accepted_in_period.append(
        ['Timestamp', 'Date', 'S0', 'S1', 'S2', 'S3', 'Total', 'Closed'])

    for x in range(-1, period_interval):
        if relative_delta == 'months':
            # make interval the first through last of month
            end_date = (start_date + relativedelta(months=x)) + relativedelta(
                day=1, months=+1, days=-1)
            new_date = (
                start_date + relativedelta(months=x)) + relativedelta(day=1)
        else:
            # week starts the monday before
            new_date = start_date + relativedelta(weeks=x, weekday=MO(1))
            end_date = new_date + relativedelta(weeks=1, weekday=MO(1))

        closed_in_range_count = findings_closed.filter(
            mitigated__date__range=[new_date, end_date]).count()

        if accepted_findings:
            risks_a = accepted_findings.filter(
                risk_acceptance__created__date__range=[
                    datetime(
                        new_date.year,
                        new_date.month,
                        1,
                        tzinfo=timezone.get_current_timezone()),
                    datetime(
                        new_date.year,
                        new_date.month,
                        monthrange(new_date.year, new_date.month)[1],
                        tzinfo=timezone.get_current_timezone())
                ])
        else:
            risks_a = None

        crit_count, high_count, med_count, low_count, closed_count = [
            0, 0, 0, 0, 0
        ]
        for finding in findings:
            if new_date <= datetime.combine(finding.date, datetime.min.time(
            )).replace(tzinfo=timezone.get_current_timezone()) <= end_date:
                if finding.severity == 'Critical':
                    crit_count += 1
                elif finding.severity == 'High':
                    high_count += 1
                elif finding.severity == 'Medium':
                    med_count += 1
                elif finding.severity == 'Low':
                    low_count += 1

        total = crit_count + high_count + med_count + low_count
        opened_in_period.append(
            [(tcalendar.timegm(new_date.timetuple()) * 1000), new_date,
             crit_count, high_count, med_count, low_count, total,
             closed_in_range_count])
        crit_count, high_count, med_count, low_count, closed_count = [
            0, 0, 0, 0, 0
        ]
        if risks_a is not None:
            for finding in risks_a:
                if finding.severity == 'Critical':
                    crit_count += 1
                elif finding.severity == 'High':
                    high_count += 1
                elif finding.severity == 'Medium':
                    med_count += 1
                elif finding.severity == 'Low':
                    low_count += 1

        total = crit_count + high_count + med_count + low_count
        accepted_in_period.append(
            [(tcalendar.timegm(new_date.timetuple()) * 1000), new_date,
             crit_count, high_count, med_count, low_count, total])

    return {
        'opened_per_period': opened_in_period,
        'accepted_per_period': accepted_in_period
    }


def get_period_counts(active_findings,
                      findings,
                      findings_closed,
                      accepted_findings,
                      period_interval,
                      start_date,
                      relative_delta='months'):
    start_date = datetime(
        start_date.year,
        start_date.month,
        start_date.day,
        tzinfo=timezone.get_current_timezone())
    opened_in_period = list()
    active_in_period = list()
    accepted_in_period = list()
    opened_in_period.append(
        ['Timestamp', 'Date', 'S0', 'S1', 'S2', 'S3', 'Total', 'Closed'])
    active_in_period.append(
        ['Timestamp', 'Date', 'S0', 'S1', 'S2', 'S3', 'Total', 'Closed'])
    accepted_in_period.append(
        ['Timestamp', 'Date', 'S0', 'S1', 'S2', 'S3', 'Total', 'Closed'])

    for x in range(-1, period_interval):
        if relative_delta == 'months':
            # make interval the first through last of month
            end_date = (start_date + relativedelta(months=x)) + relativedelta(
                day=1, months=+1, days=-1)
            new_date = (
                start_date + relativedelta(months=x)) + relativedelta(day=1)
        else:
            # week starts the monday before
            new_date = start_date + relativedelta(weeks=x, weekday=MO(1))
            end_date = new_date + relativedelta(weeks=1, weekday=MO(1))

        try:
            closed_in_range_count = findings_closed.filter(
                mitigated__date__range=[new_date, end_date]).count()
        except:
            closed_in_range_count = findings_closed.filter(
                mitigated_time__range=[new_date, end_date]).count()

        if accepted_findings:
            try:
                risks_a = accepted_findings.filter(
                    risk_acceptance__created__date__range=[
                        datetime(
                            new_date.year,
                            new_date.month,
                            1,
                            tzinfo=timezone.get_current_timezone()),
                        datetime(
                            new_date.year,
                            new_date.month,
                            monthrange(new_date.year, new_date.month)[1],
                            tzinfo=timezone.get_current_timezone())
                    ])
            except:
                risks_a = accepted_findings.filter(
                    date__range=[
                        datetime(
                            new_date.year,
                            new_date.month,
                            1,
                            tzinfo=timezone.get_current_timezone()),
                        datetime(
                            new_date.year,
                            new_date.month,
                            monthrange(new_date.year, new_date.month)[1],
                            tzinfo=timezone.get_current_timezone())
                    ])
        else:
            risks_a = None

        crit_count, high_count, med_count, low_count, closed_count = [
            0, 0, 0, 0, 0
        ]
        for finding in findings:
            try:
                severity = finding.severity
            except:
                severity = finding.finding.severity
            try:
                if new_date <= datetime.combine(
                        finding.date, datetime.min.time()
                ).replace(tzinfo=timezone.get_current_timezone()) <= end_date:
                    if severity == 'Critical':
                        crit_count += 1
                    elif severity == 'High':
                        high_count += 1
                    elif severity == 'Medium':
                        med_count += 1
                    elif severity == 'Low':
                        low_count += 1
            except:
                if new_date <= finding.date <= end_date:
                    if severity == 'Critical':
                        crit_count += 1
                    elif severity == 'High':
                        high_count += 1
                    elif severity == 'Medium':
                        med_count += 1
                    elif severity == 'Low':
                        low_count += 1
                pass

        total = crit_count + high_count + med_count + low_count
        opened_in_period.append(
            [(tcalendar.timegm(new_date.timetuple()) * 1000), new_date,
             crit_count, high_count, med_count, low_count, total,
             closed_in_range_count])
        crit_count, high_count, med_count, low_count, closed_count = [
            0, 0, 0, 0, 0
        ]
        if risks_a is not None:
            for finding in risks_a:
                try:
                    severity = finding.severity
                except:
                    severity = finding.finding.severity
                if severity == 'Critical':
                    crit_count += 1
                elif severity == 'High':
                    high_count += 1
                elif severity == 'Medium':
                    med_count += 1
                elif severity == 'Low':
                    low_count += 1

        total = crit_count + high_count + med_count + low_count
        accepted_in_period.append(
            [(tcalendar.timegm(new_date.timetuple()) * 1000), new_date,
             crit_count, high_count, med_count, low_count, total])
        crit_count, high_count, med_count, low_count, closed_count = [
            0, 0, 0, 0, 0
        ]
        for finding in active_findings:
            try:
                severity = finding.severity
            except:
                severity = finding.finding.severity
            try:
                if datetime.combine(finding.date, datetime.min.time()).replace(
                        tzinfo=timezone.get_current_timezone()) <= end_date:
                    if severity == 'Critical':
                        crit_count += 1
                    elif severity == 'High':
                        high_count += 1
                    elif severity == 'Medium':
                        med_count += 1
                    elif severity == 'Low':
                        low_count += 1
            except:
                if finding.date <= end_date:
                    if severity == 'Critical':
                        crit_count += 1
                    elif severity == 'High':
                        high_count += 1
                    elif severity == 'Medium':
                        med_count += 1
                    elif severity == 'Low':
                        low_count += 1
                pass
        total = crit_count + high_count + med_count + low_count
        active_in_period.append(
            [(tcalendar.timegm(new_date.timetuple()) * 1000), new_date,
             crit_count, high_count, med_count, low_count, total])

    return {
        'opened_per_period': opened_in_period,
        'accepted_per_period': accepted_in_period,
        'active_per_period': active_in_period
    }


def opened_in_period(start_date, end_date, pt):
    start_date = datetime(
        start_date.year,
        start_date.month,
        start_date.day,
        tzinfo=timezone.get_current_timezone())
    end_date = datetime(
        end_date.year,
        end_date.month,
        end_date.day,
        tzinfo=timezone.get_current_timezone())
    opened_in_period = Finding.objects.filter(
        date__range=[start_date, end_date],
        test__engagement__product__prod_type=pt,
        verified=True,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated__isnull=True,
        severity__in=(
            'Critical', 'High', 'Medium',
            'Low')).values('numerical_severity').annotate(
                Count('numerical_severity')).order_by('numerical_severity')
    total_opened_in_period = Finding.objects.filter(
        date__range=[start_date, end_date],
        test__engagement__product__prod_type=pt,
        verified=True,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated__isnull=True,
        severity__in=('Critical', 'High', 'Medium', 'Low')).aggregate(
            total=Sum(
                Case(
                    When(
                        severity__in=('Critical', 'High', 'Medium', 'Low'),
                        then=Value(1)),
                    output_field=IntegerField())))['total']

    oip = {
        'S0':
        0,
        'S1':
        0,
        'S2':
        0,
        'S3':
        0,
        'Total':
        total_opened_in_period,
        'start_date':
        start_date,
        'end_date':
        end_date,
        'closed':
        Finding.objects.filter(
            mitigated__date__range=[start_date, end_date],
            test__engagement__product__prod_type=pt,
            severity__in=('Critical', 'High', 'Medium', 'Low')).aggregate(
                total=Sum(
                    Case(
                        When(
                            severity__in=('Critical', 'High', 'Medium', 'Low'),
                            then=Value(1)),
                        output_field=IntegerField())))['total'],
        'to_date_total':
        Finding.objects.filter(
            date__lte=end_date.date(),
            verified=True,
            false_p=False,
            duplicate=False,
            out_of_scope=False,
            mitigated__isnull=True,
            test__engagement__product__prod_type=pt,
            severity__in=('Critical', 'High', 'Medium', 'Low')).count()
    }

    for o in opened_in_period:
        oip[o['numerical_severity']] = o['numerical_severity__count']

    return oip


class FileIterWrapper(object):
    def __init__(self, flo, chunk_size=1024**2):
        self.flo = flo
        self.chunk_size = chunk_size

    def __next__(self):
        data = self.flo.read(self.chunk_size)
        if data:
            return data
        else:
            raise StopIteration

    def __iter__(self):
        return self


def get_cal_event(start_date, end_date, summary, description, uid):
    cal = vobject.iCalendar()
    cal.add('vevent')
    cal.vevent.add('summary').value = summary
    cal.vevent.add('description').value = description
    start = cal.vevent.add('dtstart')
    start.value = start_date
    end = cal.vevent.add('dtend')
    end.value = end_date
    cal.vevent.add('uid').value = uid
    return cal


def named_month(month_number):
    """
    Return the name of the month, given the number.
    """
    return date(1900, month_number, 1).strftime("%B")


def normalize_query(query_string,
                    findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                    normspace=re.compile(r'\s{2,}').sub):
    return [
        normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)
    ]


def build_query(query_string, search_fields):
    """ Returns a query, that is a combination of Q objects. That combination
    aims to search keywords within a model by testing the given search fields.

    """
    query = None  # Query to search for every search term
    terms = normalize_query(query_string)
    for term in terms:
        or_query = None  # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})

            if or_query:
                or_query = or_query | q
            else:
                or_query = q

        if query:
            query = query & or_query
        else:
            query = or_query
    return query


def template_search_helper(fields=None, query_string=None):
    if not fields:
        fields = [
            'title',
            'description',
        ]
    findings = Finding_Template.objects.all()

    if not query_string:
        return findings

    entry_query = build_query(query_string, fields)
    found_entries = findings.filter(entry_query)

    return found_entries


def get_page_items(request, items, page_size, prefix=''):
    return get_page_items_and_count(request, items, page_size, prefix=prefix, do_count=False)


def get_page_items_and_count(request, items, page_size, prefix='', do_count=True):
    page_param = prefix + 'page'
    page_size_param = prefix + 'page_size'

    page = request.GET.get(page_param, 1)
    size = request.GET.get(page_size_param, page_size)
    paginator = Paginator(items, size)

    # new get_page method will handle invalid page value, out of bounds pages, etc
    page = paginator.get_page(page)

    # we add the total_count here which is usually before prefetching
    # which is goog in this case because for counting we don't want to join too many tables
    if do_count:
        page.total_count = paginator.count

    return page


def handle_uploaded_threat(f, eng):
    name, extension = os.path.splitext(f.name)
    with open(settings.MEDIA_ROOT + '/threat/%s%s' % (eng.id, extension),
              'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    eng.tmodel_path = settings.MEDIA_ROOT + '/threat/%s%s' % (eng.id,
                                                              extension)
    eng.save()


def handle_uploaded_selenium(f, cred):
    name, extension = os.path.splitext(f.name)
    with open(settings.MEDIA_ROOT + '/selenium/%s%s' % (cred.id, extension),
              'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    cred.selenium_script = settings.MEDIA_ROOT + '/selenium/%s%s' % (cred.id,
                                                                     extension)
    cred.save()


@dojo_model_to_id
@dojo_async_task
@app.task
@dojo_model_from_id
def add_external_issue(find, external_issue_provider):
    eng = Engagement.objects.get(test=find.test)
    prod = Product.objects.get(engagement=eng)
    logger.debug('adding external issue with provider: ' + external_issue_provider)

    if external_issue_provider == 'github':
        add_external_issue_github(find, prod, eng)


@dojo_model_to_id
@dojo_async_task
@app.task
@dojo_model_from_id
def update_external_issue(find, old_status, external_issue_provider):
    prod = Product.objects.get(engagement=Engagement.objects.get(test=find.test))
    eng = Engagement.objects.get(test=find.test)

    if external_issue_provider == 'github':
        update_external_issue_github(find, prod, eng)


@dojo_model_to_id
@dojo_async_task
@app.task
@dojo_model_from_id
def close_external_issue(find, note, external_issue_provider):
    prod = Product.objects.get(engagement=Engagement.objects.get(test=find.test))
    eng = Engagement.objects.get(test=find.test)

    if external_issue_provider == 'github':
        close_external_issue_github(find, note, prod, eng)


@dojo_model_to_id
@dojo_async_task
@app.task
@dojo_model_from_id
def reopen_external_issue(find, note, external_issue_provider):
    prod = Product.objects.get(engagement=Engagement.objects.get(test=find.test))
    eng = Engagement.objects.get(test=find.test)

    if external_issue_provider == 'github':
        reopen_external_issue_github(find, note, prod, eng)


def send_review_email(request, user, finding, users, new_note):
    # TODO remove apparent dead code

    recipients = [u.email for u in users]
    msg = "\nGreetings, \n\n"
    msg += "{0} has requested that you please review ".format(str(user))
    msg += "the following finding for accuracy:"
    msg += "\n\n" + finding.title
    msg += "\n\nIt can be reviewed at " + request.build_absolute_uri(
        reverse("view_finding", args=(finding.id, )))
    msg += "\n\n{0} provided the following details:".format(str(user))
    msg += "\n\n" + new_note.entry
    msg += "\n\nThanks\n"

    send_mail(
        'DefectDojo Finding Review Request',
        msg,
        user.email,
        recipients,
        fail_silently=False)
    pass


def process_notifications(request, note, parent_url, parent_title):
    regex = re.compile(r'(?:\A|\s)@(\w+)\b')

    usernames_to_check = set([un.lower() for un in regex.findall(note.entry)])

    users_to_notify = [
        User.objects.filter(username=username).get()
        for username in usernames_to_check
        if User.objects.filter(is_active=True, username=username).exists()
    ]  # is_staff also?

    if len(note.entry) > 200:
        note.entry = note.entry[:200]
        note.entry += "..."

    create_notification(
        event='user_mentioned',
        section=parent_title,
        note=note,
        title='%s jotted a note' % request.user,
        url=parent_url,
        icon='commenting',
        recipients=users_to_notify)


def send_atmention_email(user, users, parent_url, parent_title, new_note):
    recipients = [u.email for u in users]
    msg = "\nGreetings, \n\n"
    msg += "User {0} mentioned you in a note on {1}".format(
        str(user), parent_title)
    msg += "\n\n" + new_note.entry
    msg += "\n\nIt can be reviewed at " + parent_url
    msg += "\n\nThanks\n"
    send_mail(
        'DefectDojo - {0} @mentioned you in a note'.format(str(user)),
        msg,
        user.email,
        recipients,
        fail_silently=False)


def encrypt(key, iv, plaintext):
    text = ""
    if plaintext and plaintext is not None:
        backend = default_backend()
        cipher = Cipher(algorithms.AES(key), modes.OFB(iv), backend=backend)
        encryptor = cipher.encryptor()
        plaintext = _pad_string(plaintext)
        encrypted_text = encryptor.update(plaintext) + encryptor.finalize()
        text = binascii.b2a_hex(encrypted_text).rstrip()
    return text


def decrypt(key, iv, encrypted_text):
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.OFB(iv), backend=backend)
    encrypted_text_bytes = binascii.a2b_hex(encrypted_text)
    decryptor = cipher.decryptor()
    decrypted_text = decryptor.update(encrypted_text_bytes) + decryptor.finalize()
    decrypted_text = _unpad_string(decrypted_text)
    return decrypted_text


def _pad_string(value):
    length = len(value)
    pad_size = 16 - (length % 16)
    return value.ljust(length + pad_size, b'\x00')


def _unpad_string(value):
    if value and value is not None:
        value = value.rstrip(b'\x00')
    return value


def dojo_crypto_encrypt(plaintext):
    data = None
    if plaintext:
        key = None
        key = get_db_key()

        iv = os.urandom(16)
        data = prepare_for_save(
            iv, encrypt(key, iv, plaintext.encode('utf-8')))

    return data


def prepare_for_save(iv, encrypted_value):
    stored_value = None

    if encrypted_value and encrypted_value is not None:
        binascii.b2a_hex(encrypted_value).rstrip()
        stored_value = "AES.1:" + binascii.b2a_hex(iv).decode('utf-8') + ":" + encrypted_value.decode('utf-8')
    return stored_value


def get_db_key():
    db_key = None
    if hasattr(settings, 'DB_KEY'):
        db_key = settings.DB_KEY
        db_key = binascii.b2a_hex(
            hashlib.sha256(db_key.encode('utf-8')).digest().rstrip())[:32]

    return db_key


def prepare_for_view(encrypted_value):

    key = None
    decrypted_value = ""
    if encrypted_value is not NotImplementedError and encrypted_value is not None:
        key = get_db_key()
        encrypted_values = encrypted_value.split(":")

        if len(encrypted_values) > 1:
            type = encrypted_values[0]

            iv = binascii.a2b_hex(encrypted_values[1])
            value = encrypted_values[2]

            try:
                decrypted_value = decrypt(key, iv, value)
                decrypted_value = decrypted_value.decode('utf-8')
            except UnicodeDecodeError:
                decrypted_value = ""

    return decrypted_value


def get_system_setting(setting, default=None):
    system_settings = System_Settings.objects.get()
    return getattr(system_settings, setting, (default if default is not None else None))


@dojo_model_to_id
@dojo_async_task
@app.task
@dojo_model_from_id(model=Product)
def calculate_grade(product, *args, **kwargs):
    system_settings = System_Settings.objects.get()
    if not product:
        logger.warning('ignoring calculate product for product None!')

    if system_settings.enable_product_grade:
        logger.debug('calculating product grade for %s:%s', product.id, product.name)
        severity_values = Finding.objects.filter(
            ~Q(severity='Info'),
            active=True,
            duplicate=False,
            verified=True,
            false_p=False,
            test__engagement__product=product).values('severity').annotate(
                Count('numerical_severity')).order_by()

        low = 0
        medium = 0
        high = 0
        critical = 0
        for severity_count in severity_values:
            if severity_count['severity'] == "Critical":
                critical = severity_count['numerical_severity__count']
            elif severity_count['severity'] == "High":
                high = severity_count['numerical_severity__count']
            elif severity_count['severity'] == "Medium":
                medium = severity_count['numerical_severity__count']
            elif severity_count['severity'] == "Low":
                low = severity_count['numerical_severity__count']
        aeval = Interpreter()
        aeval(system_settings.product_grade)
        grade_product = "grade_product(%s, %s, %s, %s)" % (
            critical, high, medium, low)
        product.prod_numeric_grade = aeval(grade_product)
        product.save()


def get_celery_worker_status():
    from .tasks import celery_status
    res = celery_status.apply_async()

    # Wait 5 seconds for a response from Celery
    try:
        return res.get(timeout=5)
    except:
        return False


# Used to display the counts and enabled tabs in the product view
class Product_Tab():
    def __init__(self, product_id, title=None, tab=None):
        self.product = Product.objects.get(id=product_id)
        self.title = title
        self.tab = tab
        self.engagement_count = Engagement.objects.filter(
            product=self.product, active=True).count()
        self.open_findings_count = Finding.objects.filter(test__engagement__product=self.product,
                                                          false_p=False,
                                                          duplicate=False,
                                                          out_of_scope=False,
                                                          active=True,
                                                          mitigated__isnull=True).count()
        self.endpoints_count = Endpoint.objects.filter(
            product=self.product).count()
        self.endpoint_hosts_count = Endpoint.objects.filter(
            product=self.product).values('host').distinct().count()
        self.benchmark_type = Benchmark_Type.objects.filter(
            enabled=True).order_by('name')
        self.engagement = None

    def setTab(self, tab):
        self.tab = tab

    def setEngagement(self, engagement):
        self.engagement = engagement

    def engagement(self):
        return self.engagement

    def tab(self):
        return self.tab

    def setTitle(self, title):
        self.title = title

    def title(self):
        return self.title

    def product(self):
        return self.product

    def engagements(self):
        return self.engagement_count

    def findings(self):
        return self.open_findings_count

    def endpoints(self):
        return self.endpoints_count

    def endpoint_hosts(self):
        return self.endpoint_hosts_count

    def benchmark_type(self):
        return self.benchmark_type


# Used to display the counts and enabled tabs in the product view
def tab_view_count(product_id):
    product = Product.objects.get(id=product_id)
    engagements = Engagement.objects.filter(
        product=product, active=True).count()
    open_findings = Finding.objects.filter(test__engagement__product=product,
                                           false_p=False,
                                           duplicate=False,
                                           out_of_scope=False,
                                           active=True,
                                           mitigated__isnull=True).count()
    endpoints = Endpoint.objects.filter(product=product).count()
    # benchmarks = Benchmark_Product_Summary.objects.filter(product=product, publish=True, benchmark_type__enabled=True).order_by('benchmark_type__name')
    benchmark_type = Benchmark_Type.objects.filter(
        enabled=True).order_by('name')
    return product, engagements, open_findings, endpoints, benchmark_type


# Add a lanaguage to product
def add_language(product, language):
    prod_language = Languages.objects.filter(
        language__language__iexact=language, product=product)

    if not prod_language:
        try:
            language_type = Language_Type.objects.get(
                language__iexact=language)

            if language_type:
                lang = Languages(language=language_type, product=product)
                lang.save()
        except Language_Type.DoesNotExist:
            pass


# Apply finding template data by matching CWE + Title or CWE
def apply_cwe_to_template(finding, override=False):
    if System_Settings.objects.get().enable_template_match or override:
        # Attempt to match on CWE and Title First
        template = Finding_Template.objects.filter(
            cwe=finding.cwe, title__icontains=finding.title, template_match=True).first()

        # If none then match on CWE
        template = Finding_Template.objects.filter(
            cwe=finding.cwe, template_match=True).first()

        if template:
            finding.mitigation = template.mitigation
            finding.impact = template.impact
            finding.references = template.references
            template.last_used = timezone.now()
            template.save()

    return finding


def truncate_with_dots(the_string, max_length_including_dots):
    if not the_string:
        return the_string
    return (the_string[:max_length_including_dots - 3] + '...' if len(the_string) > max_length_including_dots else the_string)


def max_safe(list):
    return max(i for i in list if i is not None)


def get_full_url(relative_url):
    if settings.SITE_URL:
        return settings.SITE_URL + relative_url
    else:
        logger.warn('SITE URL undefined in settings, full_url cannot be created')
        return "settings.SITE_URL" + relative_url


def get_site_url():
    if settings.SITE_URL:
        return settings.SITE_URL
    else:
        logger.warn('SITE URL undefined in settings, full_url cannot be created')
        return "settings.SITE_URL"


@receiver(post_save, sender=Dojo_User)
def set_default_notifications(sender, instance, created, **kwargs):
    # for new user we create a Notifications object so the default 'alert' notifications work
    # this needs to be a signal to make it also work for users created via ldap, oauth and other authentication backends
    if created:
        logger.info('creating default set of notifications for: ' + str(instance))
        notifications = Notifications()
        notifications.user = instance
        notifications.save()


@receiver(post_save, sender=Engagement)
def engagement_post_Save(sender, instance, created, **kwargs):
    if created:
        engagement = instance
        title = 'Engagement created for ' + str(engagement.product) + ': ' + str(engagement.name)
        create_notification(event='engagement_added', title=title, engagement=engagement, product=engagement.product,
                            url=reverse('view_engagement', args=(engagement.id,)))


def merge_sets_safe(set1, set2):
    return set(itertools.chain(set1 or [], set2 or []))
    # This concat looks  better, but requires Python 3.6+
    # return {*set1, *set2}


def is_safe_url(url):
    try:
        # available in django 3+
        from django.utils.http import url_has_allowed_host_and_scheme
    except ImportError:
        # django < 3
        from django.utils.http import \
            is_safe_url as url_has_allowed_host_and_scheme

    return url_has_allowed_host_and_scheme(url, allowed_hosts=None)


def get_return_url(request):
    return_url = request.POST.get('return_url', None)
    # print('return_url from POST: ', return_url)
    if return_url is None or not return_url.strip():
        # for some reason using request.GET.get('return_url') never works
        return_url = request.GET['return_url'] if 'return_url' in request.GET else None
        # print('return_url from GET: ', return_url)

    return return_url if return_url else None


def redirect_to_return_url_or_else(request, or_else):
    return_url = get_return_url(request)

    if return_url:
        # logger.debug('redirecting to %s: ', return_url.strip())
        return redirect(request, return_url.strip())
    elif or_else:
        return redirect(request, or_else)
    else:
        messages.add_message(request, messages.ERROR, 'Unable to redirect anywhere.', extra_tags='alert-danger')
        return redirect(request, request.get_full_path())


def redirect(request, redirect_to):
    """Only allow redirects to allowed_hosts to prevent open redirects"""
    if is_safe_url(redirect_to):
        return HttpResponseRedirect(redirect_to)
    raise ValueError('invalid redirect, host and scheme not in allowed_hosts')


def file_size_mb(file_obj):
    if file_obj:
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(0, 0)
        if size > 0:
            return size / 1048576
    return 0


def is_scan_file_too_large(scan_file):
    if hasattr(settings, "SCAN_FILE_MAX_SIZE"):
        size = file_size_mb(scan_file)
        if size > settings.SCAN_FILE_MAX_SIZE:
            return True
    return False


def queryset_check(query):
    return query if isinstance(query, QuerySet) else query.qs


def sla_compute_and_notify(*args, **kwargs):
    """
    The SLA computation and notification will be disabled if the user opts out
    of the Findings SLA on the System Settings page.

    Notifications are managed the usual way, so you'd have to opt-in.
    Exception is for JIRA issues, which would get a comment anyways.
    """
    import dojo.jira_link.helper as jira_helper

    def _notify(finding, title):
        create_notification(
            event='sla_breach',
            title=title,
            finding=finding,
            sla_age=sla_age
        )

        if do_jira_sla_comment:
            logger.info("Creating JIRA comment to notify of SLA breach information.")
            jira_helper.add_simple_jira_comment(jira_instance, jira_issue, title)

    # exit early on flags
    if not settings.SLA_NOTIFY_ACTIVE and not settings.SLA_NOTIFY_ACTIVE_VERIFIED_ONLY:
        logger.info("Will not notify on SLA breach per user configured settings")
        return

    jira_issue = None
    jira_instance = None
    try:
        system_settings = System_Settings.objects.get()
        if system_settings.enable_finding_sla:
            logger.info("About to process findings for SLA notifications.")
            logger.debug("Active {}, Verified {}, Has JIRA {}, pre-breach {}, post-breach {}".format(
                settings.SLA_NOTIFY_ACTIVE,
                settings.SLA_NOTIFY_ACTIVE_VERIFIED_ONLY,
                settings.SLA_NOTIFY_WITH_JIRA_ONLY,
                settings.SLA_NOTIFY_PRE_BREACH,
                settings.SLA_NOTIFY_POST_BREACH,
            ))

            query = None
            if settings.SLA_NOTIFY_ACTIVE:
                query = Q(active=True, is_mitigated=False, duplicate=False)
            if settings.SLA_NOTIFY_ACTIVE_VERIFIED_ONLY:
                query = Q(active=True, verified=True, is_mitigated=False, duplicate=False)
            logger.debug("My query: {}".format(query))

            no_jira_findings = {}
            if settings.SLA_NOTIFY_WITH_JIRA_ONLY:
                logger.debug("Ignoring findings that are not linked to a JIRA issue")
                no_jira_findings = Finding.objects.exclude(jira_issue__isnull=False)

            total_count = 0
            pre_breach_count = 0
            post_breach_count = 0
            post_breach_no_notify_count = 0
            jira_count = 0
            at_breach_count = 0

            # Taking away for now, since the prefetch is not efficient
            # .select_related('jira_issue') \
            # .prefetch_related(Prefetch('test__engagement__product__jira_project_set__jira_instance')) \
            # A finding with 'Info' severity will not be considered for SLA notifications (not in model)
            findings = Finding.objects \
                .filter(query) \
                .exclude(severity='Info') \
                .exclude(id__in=no_jira_findings)

            for finding in findings:
                total_count += 1
                sla_age = finding.sla_days_remaining()
                # if SLA is set to 0 in settings, it's a null. And setting at 0 means no SLA apparently.
                if sla_age is None:
                    sla_age = 0

                if (sla_age < 0) and (settings.SLA_NOTIFY_POST_BREACH < abs(sla_age)):
                    post_breach_no_notify_count += 1
                    # Skip finding notification if breached for too long
                    logger.debug("Finding {} breached the SLA {} days ago. Skipping notifications.".format(finding.id, abs(sla_age)))
                    continue

                do_jira_sla_comment = False
                jira_issue = None
                if finding.has_jira_issue:
                    jira_issue = finding.jira_issue
                elif finding.grouped:
                    jira_issue = finding.finding_group.jira_issue

                if jira_issue:
                    jira_count += 1
                    jira_instance = jira_helper.get_jira_instance(finding)
                    if jira_instance is not None:
                        logger.debug("JIRA config for finding is {}".format(jira_instance))
                        # global config or product config set, product level takes precedence
                        try:
                            # TODO: see new property from #2649 to then replace, somehow not working with prefetching though.
                            product_jira_sla_comment_enabled = jira_helper.get_jira_project(finding).product_jira_sla_notification
                        except Exception as e:
                            logger.error("The product is not linked to a JIRA configuration! Something is weird here.")
                            logger.error("Error is: {}".format(e))

                        jiraconfig_sla_notification_enabled = jira_instance.global_jira_sla_notification

                        if jiraconfig_sla_notification_enabled or product_jira_sla_comment_enabled:
                            logger.debug("Global setting {} -- Product setting {}".format(
                                jiraconfig_sla_notification_enabled,
                                product_jira_sla_comment_enabled
                            ))
                            do_jira_sla_comment = True
                            logger.debug("JIRA issue is {}".format(jira_issue.jira_key))

                logger.debug("Finding {} has {} days left to breach SLA.".format(finding.id, sla_age))
                if (sla_age < 0):
                    post_breach_count += 1
                    logger.info("Finding {} has breached by {} days.".format(finding.id, abs(sla_age)))
                    _notify(finding, 'Finding {} - SLA breached by {} day(s)! Overdue notice'.format(finding.id, abs(sla_age)))
                # The finding is within the pre-breach period
                elif (sla_age > 0) and (sla_age <= settings.SLA_NOTIFY_PRE_BREACH):
                    pre_breach_count += 1
                    logger.info("Security SLA pre-breach warning for finding ID {}. Days remaining: {}".format(finding.id, sla_age))
                    _notify(finding, 'Finding {} - SLA pre-breach warning - {} day(s) left'.format(finding.id, sla_age))
                # The finding breaches the SLA today
                elif (sla_age == 0):
                    at_breach_count += 1
                    logger.info("Security SLA breach warning. Finding ID {} breaching today ({})".format(finding.id, sla_age))
                    _notify(finding, "Finding {} - SLA is breaching today".format(finding.id))

            logger.info("SLA run results: Pre-breach: {}, at-breach: {}, post-breach: {} post-breach-no-notify: {}, with-jira: {}, TOTAL: {}".format(
                pre_breach_count,
                at_breach_count,
                post_breach_count,
                post_breach_no_notify_count,
                jira_count,
                total_count
            ))

    except System_Settings.DoesNotExist:
        logger.info("Findings SLA is not enabled.")


def get_words_for_field(model, fieldname):
    max_results = getattr(settings, 'MAX_AUTOCOMPLETE_WORDS', 20000)
    models = None
    if model == Finding:
        models = get_authorized_findings(Permissions.Finding_View, user=get_current_user())
    elif model == Finding_Template:
        models = Finding_Template.objects.all()

    if models is not None:
        words = [
            word for field_value in models.order_by().filter(**{'%s__isnull' % fieldname: False}).values_list(fieldname, flat=True).distinct()[:max_results] for word in (field_value.split() if field_value else []) if len(word) > 2
        ]
    else:
        words = []

    return sorted(set(words))


def get_current_user():
    return crum.get_current_user()


def get_current_request():
    return crum.get_current_request()


def create_bleached_link(url, title):
    link = '<a href=\"'
    link += url
    link += '\" target=\"_blank\" title=\"'
    link += title
    link += '\">'
    link += title
    link += '</a>'
    return bleach.clean(link, tags=['a'], attributes={'a': ['href', 'target', 'title']})


def get_object_or_none(klass, *args, **kwargs):
    """
    Use get() to return an object, or return None
    does not exist.
    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.
    Like with QuerySet.get(), MultipleObjectsReturned is raised if more than
    one object is found.
    """
    queryset = klass

    if hasattr(klass, '_default_manager'):
        queryset = klass._default_manager.all()

    if not hasattr(queryset, 'get'):
        klass__name = klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        raise ValueError(
            "First argument to get_object_or_None() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist:
        return None


def add_success_message_to_response(message):
    if get_current_request():
        messages.add_message(get_current_request(),
                            messages.SUCCESS,
                            message,
                            extra_tags='alert-success')


def add_error_message_to_response(message):
    if get_current_request():
        messages.add_message(get_current_request(),
                            messages.ERROR,
                            message,
                            extra_tags='alert-danger')


def add_field_errors_to_response(form):
    if form and get_current_request():
        for field, error in form.errors.items():
            add_error_message_to_response(error)


def mass_model_updater(model_type, models, function, fields, page_size=1000, order='asc', log_prefix=''):
    """ Using the default for model in queryset can be slow for large querysets. Even
    when using paging as LIMIT and OFFSET are slow on database. In some cases we can optimize
    this process very well if we can process the models ordered by id.
    In that case we don't need LIMIT or OFFSET, but can keep track of the latest id that
    was processed and continue from there on the next page. This is fast because
    it results in an index seek instead of executing the whole query again and skipping
    the first X items.
    """
    # force ordering by id to make our paging work
    last_id = None
    models = models.order_by()
    if order == 'asc':
        logger.debug('ordering ascending')
        models = models.order_by('id')
        last_id = 0
    elif order == 'desc':
        logger.debug('ordering descending')
        models = models.order_by('-id')
        # get maximum, which is the first due to descending order
        last_id = models.first().id + 1
    else:
        raise ValueError('order must be ''asc'' or ''desc''')
    # use filter to make count fast on mysql
    total_count = models.filter(id__gt=0).count()
    logger.debug('%s found %d models for mass update:', log_prefix, total_count)

    i = 0
    batch = []
    total_pages = (total_count // page_size) + 2
    # logger.info('pages to process: %d', total_pages)
    logger.info('%s%s out of %s models processed ...', log_prefix, i, total_count)
    for p in range(1, total_pages):
        # logger.info('page: %d', p)
        if order == 'asc':
            page = models.filter(id__gt=last_id)[:page_size]
        else:
            page = models.filter(id__lt=last_id)[:page_size]

        # logger.info('page query: %s', page.query)
        # if p == 23:
        #     raise ValueError('bla')
        for model in page:
            i += 1
            last_id = model.id
            # logger.info('last_id: %s', last_id)

            function(model)

            batch.append(model)

            if (i > 0 and i % page_size == 0):
                if fields:
                    model_type.objects.bulk_update(batch, fields)
                batch = []
                logger.info('%s%s out of %s models processed ...', log_prefix, i, total_count)

    if fields:
        model_type.objects.bulk_update(batch, fields)
    batch = []
    logger.info('%s%s out of %s models processed ...', log_prefix, i, total_count)


def to_str_typed(obj):
    """ for code that handles multiple types of objects, print not only __str__ but prefix the type of the object"""
    return '%s: %s' % (type(obj), obj)


def get_product(obj):
    logger.debug('getting product for %s:%s', type(obj), obj)
    if not obj:
        return None

    if type(obj) == Finding or type(obj) == Finding_Group:
        return obj.test.engagement.product

    if type(obj) == Test:
        return obj.engagement.product

    if type(obj) == Engagement:
        return obj.product

    if type(obj) == Product:
        return obj


def prod_name(obj):
    if not obj:
        return 'Unknown'

    return get_product(obj).name


# Returns image locations by default (i.e. uploaded_files/09577eb1-6ccb-430b-bc82-0742d4c97a09.png)
# if return_objects=True, return the FileUPload object instead of just the file location
def get_file_images(obj, return_objects=False):
    logger.debug('getting images for %s:%s', type(obj), obj)
    files = None
    if not obj:
        return files
    files = obj.files.all()

    images = []
    for file in files:
        file_name = file.file.name
        file_type = mimetypes.guess_type(file_name)[0]
        if file_type and 'image' in file_type:
            if return_objects:
                images.append(file)
            else:
                images.append(file_name)
    return images
