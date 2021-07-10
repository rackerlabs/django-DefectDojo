# #  findings
import base64
import json
import logging
import mimetypes
from collections import OrderedDict, defaultdict
from django.db import models
from django.db.models.functions import Length
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import serializers
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.http import StreamingHttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import formats
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.views.decorators.http import require_POST
from itertools import chain
from imagekit import ImageSpec
from imagekit.processors import ResizeToFill
from dojo.utils import add_error_message_to_response, add_field_errors_to_response, add_success_message_to_response, close_external_issue, redirect, reopen_external_issue
import copy

from dojo.filters import OpenFindingFilter, AcceptedFindingFilter, ClosedFindingFilter, TemplateFindingFilter, SimilarFindingFilter
from dojo.forms import NoteForm, TypedNoteForm, CloseFindingForm, FindingForm, PromoteFindingForm, FindingTemplateForm, \
    DeleteFindingTemplateForm, JIRAFindingForm, GITHUBFindingForm, ReviewFindingForm, ClearFindingReviewForm, \
    DefectFindingForm, StubFindingForm, DeleteFindingForm, DeleteStubFindingForm, ApplyFindingTemplateForm, \
    FindingFormID, FindingBulkUpdateForm, MergeFindings
from dojo.models import Finding, Finding_Group, Notes, NoteHistory, Note_Type, \
    BurpRawRequestResponse, Stub_Finding, Endpoint, Finding_Template, Endpoint_Status, \
    FileAccessToken, GITHUB_PKey, GITHUB_Issue, Dojo_User, Cred_Mapping, Test, Product, User, Engagement
from dojo.utils import get_page_items, add_breadcrumb, FileIterWrapper, process_notifications, \
    get_system_setting, apply_cwe_to_template, Product_Tab, calculate_grade, \
    redirect_to_return_url_or_else, get_return_url, add_external_issue, update_external_issue, \
    get_words_for_field
from dojo.notifications.helper import create_notification

from django.template.defaultfilters import pluralize
from django.db.models import Q, QuerySet, Count
import dojo.jira_link.helper as jira_helper
import dojo.risk_acceptance.helper as ra_helper
import dojo.finding.helper as finding_helper
from dojo.authorization.authorization import user_has_permission_or_403
from dojo.authorization.authorization_decorators import user_is_authorized
from dojo.authorization.roles_permissions import Permissions
from dojo.finding.queries import get_authorized_findings

logger = logging.getLogger(__name__)


def open_findings_filter(request, queryset, user, pid):
    return OpenFindingFilter(request.GET, queryset=queryset, user=user, pid=pid)


def accepted_findings_filter(request, queryset, user, pid):
    return AcceptedFindingFilter(request.GET, queryset=queryset, user=user, pid=pid)


def closed_findings_filter(request, queryset, user, pid):
    return ClosedFindingFilter(request.GET, queryset=queryset, user=user, pid=pid)


def open_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="Open", query_filter=finding_helper.OPEN_FINDINGS_QUERY, prefetch_type='open')


def verified_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="Verified", query_filter=finding_helper.VERIFIED_FINDINGS_QUERY)


def out_of_scope_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="Out of Scope", query_filter=finding_helper.OUT_OF_SCOPE_FINDINGS_QUERY)


def false_positive_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="False Positive", query_filter=finding_helper.FALSE_POSITIVE_FINDINGS_QUERY)


def inactive_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="Inactive", query_filter=finding_helper.INACTIVE_FINDINGS_QUERY)


def accepted_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="Accepted", query_filter=finding_helper.ACCEPTED_FINDINGS_QUERY,
                    django_filter=accepted_findings_filter)


def closed_findings(request, pid=None, eid=None, view=None):
    return findings(request, pid=pid, eid=eid, view=view, filter_name="Closed", query_filter=finding_helper.CLOSED_FINDINGS_QUERY, order_by=('-mitigated'),
                    django_filter=closed_findings_filter)


def findings(request, pid=None, eid=None, view=None, filter_name=None, query_filter=None, order_by='numerical_severity',
django_filter=open_findings_filter, prefetch_type='all'):

    show_product_column = True
    custom_breadcrumb = None
    product_tab = None
    jira_project = None
    github_config = None

    findings = get_authorized_findings(Permissions.Finding_View)
    # print('View: ', view)
    if view == "All":
        filter_name = "All"
    else:
        print('Filtering!', view)
        findings = findings.filter(query_filter)

    findings = findings.order_by(order_by)
    # print('findings.query1', findings.query)

    if pid:
        product = get_object_or_404(Product, id=pid)
        findings = findings.filter(test__engagement__product__id=pid)

        show_product_column = False
        product_tab = Product_Tab(pid, title="Findings", tab="findings")
        jira_project = jira_helper.get_jira_project(product)
        github_config = GITHUB_PKey.objects.filter(product=pid).first()

    elif eid:
        engagement = get_object_or_404(Engagement, id=eid)
        findings = findings.filter(test__engagement=eid)

        show_product_column = False
        product_tab = Product_Tab(engagement.product_id, title=engagement.name, tab="engagements")
        jira_project = jira_helper.get_jira_project(engagement)
        github_config = GITHUB_PKey.objects.filter(product__engagement=eid).first()
    else:
        add_breadcrumb(title="Findings", top_level=not len(request.GET), request=request)

    print('findings.query2', findings.query)
    # print(django_filter)
    findings_filter = django_filter(request, findings, request.user, pid)

    print('findings.query3', findings_filter.qs.query)

    print('done')

    title_words = get_words_for_field(Finding, 'title')
    component_words = get_words_for_field(Finding, 'component_name')

    # trick to prefetch after paging to avoid huge join generated by select count(*) from Paginator
    paged_findings = get_page_items(request, findings_filter.qs, 25)

    paged_findings.object_list = prefetch_for_findings(paged_findings.object_list, prefetch_type)

    bulk_edit_form = FindingBulkUpdateForm(request.GET)

    # show custom breadcrumb if user has filtered by exactly 1 endpoint
    endpoint = None
    if 'endpoints' in request.GET:
        endpoints = request.GET.getlist('endpoints', [])
        if len(endpoints) == 1:
            endpoint = endpoints[0]
            endpoint = get_object_or_404(Endpoint, id=endpoint)
            pid = endpoint.product.id
            filter_name = "Vulnerable Endpoints"
            custom_breadcrumb = OrderedDict([("Endpoints", reverse('vulnerable_endpoints')), (endpoint, reverse('view_endpoint', args=(endpoint.id, )))])

    if github_config:
        github_config = github_config.git_conf_id

    return render(
        request, 'dojo/findings_list.html', {
            'show_product_column': show_product_column,
            "product_tab": product_tab,
            "findings": paged_findings,
            "filtered": findings_filter,
            "title_words": title_words,
            "component_words": component_words,
            'custom_breadcrumb': custom_breadcrumb,
            'filter_name': filter_name,
            'jira_project': jira_project,
            'bulk_edit_form': bulk_edit_form,
        })


def prefetch_for_findings(findings, prefetch_type='all'):
    prefetched_findings = findings
    if isinstance(findings, QuerySet):  # old code can arrive here with prods being a list because the query was already executed
        prefetched_findings = prefetched_findings.prefetch_related('reporter')
        prefetched_findings = prefetched_findings.prefetch_related('jira_issue__jira_project__jira_instance')
        prefetched_findings = prefetched_findings.prefetch_related('test__test_type')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__jira_project__jira_instance')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__jira_project_set__jira_instance')
        prefetched_findings = prefetched_findings.prefetch_related('found_by')

        # for open/active findings the following 4 prefetches are not needed
        if prefetch_type != 'open':
            prefetched_findings = prefetched_findings.prefetch_related('risk_acceptance_set')
            prefetched_findings = prefetched_findings.prefetch_related('risk_acceptance_set__accepted_findings')
            prefetched_findings = prefetched_findings.prefetch_related('original_finding')
            prefetched_findings = prefetched_findings.prefetch_related('duplicate_finding')

        prefetched_findings = prefetched_findings.prefetch_related('test_import_finding_action_set')
        # we could try to prefetch only the latest note with SubQuery and OuterRef, but I'm getting that MySql doesn't support limits in subqueries.
        prefetched_findings = prefetched_findings.prefetch_related('notes')
        prefetched_findings = prefetched_findings.prefetch_related('tags')
        prefetched_findings = prefetched_findings.prefetch_related('endpoints')
        prefetched_findings = prefetched_findings.prefetch_related('endpoint_status')
        prefetched_findings = prefetched_findings.prefetch_related('endpoint_status__endpoint')
        prefetched_findings = prefetched_findings.annotate(active_endpoint_count=Count('endpoint_status__id', filter=Q(endpoint_status__mitigated=False)))
        prefetched_findings = prefetched_findings.annotate(mitigated_endpoint_count=Count('endpoint_status__id', filter=Q(endpoint_status__mitigated=True)))
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__authorized_users')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__prod_type__authorized_users')
        prefetched_findings = prefetched_findings.prefetch_related('finding_group_set')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__members')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__prod_type__members')
    else:
        logger.debug('unable to prefetch because query was already executed')

    return prefetched_findings


def prefetch_for_similar_findings(findings):
    prefetched_findings = findings
    if isinstance(findings, QuerySet):  # old code can arrive here with prods being a list because the query was already executed
        prefetched_findings = prefetched_findings.prefetch_related('reporter')
        prefetched_findings = prefetched_findings.prefetch_related('jira_issue__jira_project__jira_instance')
        prefetched_findings = prefetched_findings.prefetch_related('test__test_type')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__jira_project__jira_instance')
        prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__jira_project_set__jira_instance')
        prefetched_findings = prefetched_findings.prefetch_related('found_by')
        prefetched_findings = prefetched_findings.prefetch_related('risk_acceptance_set')
        prefetched_findings = prefetched_findings.prefetch_related('risk_acceptance_set__accepted_findings')
        prefetched_findings = prefetched_findings.prefetch_related('original_finding')
        prefetched_findings = prefetched_findings.prefetch_related('duplicate_finding')
        prefetched_findings = prefetched_findings.prefetch_related('test_import_finding_action_set')
        # we could try to prefetch only the latest note with SubQuery and OuterRef, but I'm getting that MySql doesn't support limits in subqueries.
        prefetched_findings = prefetched_findings.prefetch_related('notes')
        prefetched_findings = prefetched_findings.prefetch_related('tags')
        # prefetched_findings = prefetched_findings.prefetch_related('endpoints')
        # prefetched_findings = prefetched_findings.prefetch_related('endpoint_status')
        # prefetched_findings = prefetched_findings.prefetch_related('endpoint_status__endpoint')
        # prefetched_findings = prefetched_findings.annotate(active_endpoint_count=Count('endpoint_status__id', filter=Q(endpoint_status__mitigated=False)))
        # prefetched_findings = prefetched_findings.annotate(mitigated_endpoint_count=Count('endpoint_status__id', filter=Q(endpoint_status__mitigated=True)))
        # prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__authorized_users')
        # prefetched_findings = prefetched_findings.prefetch_related('test__engagement__product__prod_type__authorized_users')
    else:
        logger.debug('unable to prefetch because query was already executed')

    return prefetched_findings


@user_is_authorized(Finding, Permissions.Finding_View, 'fid', 'view')
def view_finding(request, fid):
    finding_qs = prefetch_for_findings(Finding.objects.all())
    finding = get_object_or_404(finding_qs, id=fid)
    findings = Finding.objects.filter(test=finding.test).order_by('numerical_severity').values_list('id', flat=True)
    logger.debug(findings)
    try:
        prev_finding_id = findings[(list(findings).index(finding.id)) - 1]
    except AssertionError:
        prev_finding_id = finding.id
    try:
        next_finding_id = findings[(list(findings).index(finding.id)) + 1]
    except IndexError:
        next_finding_id = finding.id

    cred_finding = Cred_Mapping.objects.filter(
        finding=finding.id).select_related('cred_id').order_by('cred_id')
    creds = Cred_Mapping.objects.filter(
        test=finding.test.id).select_related('cred_id').order_by('cred_id')
    cred_engagement = Cred_Mapping.objects.filter(
        engagement=finding.test.engagement.id).select_related(
            'cred_id').order_by('cred_id')
    user = request.user
    cwe_template = None
    try:
        cwe_template = Finding_Template.objects.filter(cwe=finding.cwe).first()
    except Finding_Template.DoesNotExist:
        pass

    dojo_user = get_object_or_404(Dojo_User, id=user.id)

    notes = finding.notes.all()
    files = finding.files.all()
    note_type_activation = Note_Type.objects.filter(is_active=True).count()
    if note_type_activation:
        available_note_types = find_available_notetypes(notes)
    if request.method == 'POST':
        if note_type_activation:
            form = TypedNoteForm(request.POST, available_note_types=available_note_types)
        else:
            form = NoteForm(request.POST)
        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            history = NoteHistory(data=new_note.entry,
                                  time=new_note.date,
                                  current_editor=new_note.author)
            history.save()
            new_note.history.add(history)
            finding.notes.add(new_note)
            finding.last_reviewed = new_note.date
            finding.last_reviewed_by = user
            finding.save()

            if finding.has_jira_issue:
                jira_helper.add_comment(finding, new_note)
            elif finding.has_jira_group_issue:
                jira_helper.add_comment(finding.finding_group, new_note)

            if note_type_activation:
                form = TypedNoteForm(available_note_types=available_note_types)
            else:
                form = NoteForm()
            url = request.build_absolute_uri(
                reverse("view_finding", args=(finding.id, )))
            title = "Finding: " + finding.title
            process_notifications(request, new_note, url, title)
            messages.add_message(
                request,
                messages.SUCCESS,
                'Note saved.',
                extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('view_finding', args=(finding.id, )))
    else:
        if note_type_activation:
            form = TypedNoteForm(available_note_types=available_note_types)
        else:
            form = NoteForm()

    try:
        reqres = BurpRawRequestResponse.objects.get(finding=finding)
        burp_request = base64.b64decode(reqres.burpRequestBase64)
        burp_response = base64.b64decode(reqres.burpResponseBase64)
    except:
        reqres = None
        burp_request = None
        burp_response = None

    # add related actions for non-similar and non-duplicate cluster members
    finding.related_actions = calculate_possible_related_actions_for_similar_finding(request, finding, finding)
    if finding.duplicate_finding:
        finding.duplicate_finding.related_actions = calculate_possible_related_actions_for_similar_finding(request, finding, finding.duplicate_finding)

    similar_findings_filter = SimilarFindingFilter(request.GET, queryset=get_authorized_findings(Permissions.Finding_View), user=request.user, finding=finding)
    logger.debug('similar query: %s', similar_findings_filter.qs.query)

    similar_findings = get_page_items(request, similar_findings_filter.qs, settings.SIMILAR_FINDINGS_MAX_RESULTS, prefix='similar')

    similar_findings.object_list = prefetch_for_similar_findings(similar_findings.object_list)

    for similar_finding in similar_findings:
        similar_finding.related_actions = calculate_possible_related_actions_for_similar_finding(request, finding, similar_finding)

    product_tab = Product_Tab(finding.test.engagement.product.id, title="View Finding", tab="findings")

    can_be_pushed_to_jira, can_be_pushed_to_jira_error, error_code = jira_helper.can_be_pushed_to_jira(finding)

    lastPos = (len(findings)) - 1
    return render(
        request, 'dojo/view_finding.html', {
            'product_tab': product_tab,
            'finding': finding,
            'burp_request': burp_request,
            'cred_finding': cred_finding,
            'creds': creds,
            'cred_engagement': cred_engagement,
            'burp_response': burp_response,
            'dojo_user': dojo_user,
            'user': user,
            'notes': notes,
            'files': files,
            'form': form,
            'cwe_template': cwe_template,
            'found_by': finding.found_by.all().distinct(),
            'findings_list': findings,
            'findings_list_lastElement': findings[lastPos],
            'prev_finding_id': prev_finding_id,
            'next_finding_id': next_finding_id,
            'duplicate_cluster': duplicate_cluster(request, finding),
            'similar_findings': similar_findings,
            'similar_findings_filter': similar_findings_filter,
            'can_be_pushed_to_jira': can_be_pushed_to_jira,
            'can_be_pushed_to_jira_error': can_be_pushed_to_jira_error,
        })


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'change')
def close_finding(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    # in order to close a finding, we need to capture why it was closed
    # we can do this with a Note
    note_type_activation = Note_Type.objects.filter(is_active=True)
    if len(note_type_activation):
        missing_note_types = get_missing_mandatory_notetypes(finding)
    else:
        missing_note_types = note_type_activation
    form = CloseFindingForm(missing_note_types=missing_note_types)
    if request.method == 'POST':
        form = CloseFindingForm(request.POST, missing_note_types=missing_note_types)

        close_external_issue(finding, 'Closed by defectdojo', 'github')

        if form.is_valid():
            now = timezone.now()
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = now
            new_note.save()
            finding.notes.add(new_note)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Note Saved.',
                extra_tags='alert-success')

            if len(missing_note_types) == 0:
                finding.active = False
                now = timezone.now()
                finding.mitigated = now
                finding.mitigated_by = request.user
                finding.is_mitigated = True
                finding.last_reviewed = finding.mitigated
                finding.last_reviewed_by = request.user
                endpoint_status = finding.endpoint_status.all()
                for status in endpoint_status:
                    status.mitigated_by = request.user
                    status.mitigated_time = timezone.now()
                    status.mitigated = True
                    status.last_modified = timezone.now()
                    status.save()

                # only push to JIRA if there is an issue, to prevent a new one from being created
                if jira_helper.is_push_all_issues(finding) and finding.has_jira_issue:
                    finding.save(push_to_jira=True)
                else:
                    finding.save()

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Finding closed.',
                    extra_tags='alert-success')
                create_notification(event='other',
                                    title='Closing of %s' % finding.title,
                                    finding=finding,
                                    description='The finding "%s" was closed by %s' % (finding.title, request.user),
                                    url=request.build_absolute_uri(reverse('view_test', args=(finding.test.id, ))),
                                    )
                return HttpResponseRedirect(
                    reverse('view_test', args=(finding.test.id, )))
            else:
                return HttpResponseRedirect(
                    reverse('close_finding', args=(finding.id, )))

    else:
        form = CloseFindingForm(missing_note_types=missing_note_types)

    product_tab = Product_Tab(finding.test.engagement.product.id, title="Close", tab="findings")

    return render(request, 'dojo/close_finding.html', {
        'finding': finding,
        'product_tab': product_tab,
        'active_tab': 'findings',
        'user': request.user,
        'form': form,
        'note_types': missing_note_types
    })


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'staff')
def defect_finding_review(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    # in order to close a finding, we need to capture why it was closed
    # we can do this with a Note
    if request.method == 'POST':
        form = DefectFindingForm(request.POST)

        if form.is_valid():
            now = timezone.now()
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = now
            new_note.save()
            finding.notes.add(new_note)
            finding.under_defect_review = False
            defect_choice = form.cleaned_data['defect_choice']

            if defect_choice == "Close Finding":
                finding.active = False
                finding.mitigated = now
                finding.mitigated_by = request.user
                finding.is_mitigated = True
                finding.last_reviewed = finding.mitigated
                finding.last_reviewed_by = request.user
                finding.endpoints.clear()

            # TODO: JIRA: Code below should move to jira_helper. But I have no idea what it is doin so don't want move/break it

            jira = jira_helper.get_jira_connection(finding)
            if jira and finding.has_jira_issue:
                j_issue = finding.jira_issue
                issue = jira.issue(j_issue.jira_id)

                if defect_choice == "Close Finding":
                    # If the issue id is closed jira will return Reopen Issue
                    resolution_id = jira_helper.jira_get_resolution_id(jira, issue,
                                                           "Reopen Issue")
                    if resolution_id is None:
                        resolution_id = jira_helper.jira_get_resolution_id(
                            jira, issue, "Resolve Issue")
                        jira_helper.jira_transition(jira, issue, resolution_id)
                        new_note.entry = new_note.entry + "\nJira issue set to resolved."
                else:
                    # Re-open finding with notes stating why re-open
                    resolution_id = jira_helper.jira_get_resolution_id(jira, issue,
                                                        "Resolve Issue")
                    if resolution_id is not None:
                        jira_helper.jira_transition(jira, issue, resolution_id)
                        new_note.entry = new_note.entry + "\nJira issue re-opened."

            # Update Dojo and Jira with a notes
            if finding.has_jira_issue:
                jira_helper.add_comment(finding, new_note, force_push=True)
            elif finding.has_jira_group_issue:
                jira_helper.add_comment(finding.finding_group, new_note, force_push=True)

            finding.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Defect Reviewed',
                extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('view_test', args=(finding.test.id, )))

    else:
        form = DefectFindingForm()

    product_tab = Product_Tab(finding.test.engagement.product.id, title="Jira Status Review", tab="findings")

    return render(request, 'dojo/defect_finding_review.html', {
        'finding': finding,
        'product_tab': product_tab,
        'user': request.user,
        'form': form
    })


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'change')
def reopen_finding(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    finding.active = True
    finding.mitigated = None
    finding.mitigated_by = request.user
    finding.is_mitigated = False
    finding.last_reviewed = finding.mitigated
    finding.last_reviewed_by = request.user
    endpoint_status = finding.endpoint_status.all()
    for status in endpoint_status:
        status.mitigated_by = None
        status.mitigated_time = None
        status.mitigated = False
        status.last_modified = timezone.now()
        status.save()

    # only push to JIRA if there is an issue, otherwise a new one is created
    if jira_helper.is_push_all_issues(finding) and finding.has_jira_issue:
        finding.save(push_to_jira=True)
    else:
        finding.save()

    reopen_external_issue(finding, 're-opened by defectdojo', 'github')

    messages.add_message(
        request,
        messages.SUCCESS,
        'Finding Reopened.',
        extra_tags='alert-success')
    create_notification(event='other',
                        title='Reopening of %s' % finding.title,
                        finding=finding,
                        description='The finding "%s" was reopened by %s' % (finding.title, request.user),
                        url=request.build_absolute_uri(reverse('view_test', args=(finding.test.id, ))),
                        )
    return HttpResponseRedirect(reverse('view_finding', args=(finding.id, )))


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'staff')
def apply_template_cwe(request, fid):
    finding = get_object_or_404(Finding, id=fid)

    form = FindingFormID(instance=finding)

    if request.method == 'POST':
        form = FindingFormID(request.POST, instance=finding)
        if form.is_valid():
            finding = apply_cwe_to_template(finding)
            finding.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding CWE template applied successfully.',
                extra_tags='alert-success')
            return HttpResponseRedirect(reverse('view_finding', args=(fid, )))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'Unable to apply CWE template finding, please try again.',
                extra_tags='alert-danger')
    else:
        return HttpResponseForbidden()


@user_is_authorized(Finding, Permissions.Finding_Delete, 'fid', 'delete')
def delete_finding(request, fid):
    finding = get_object_or_404(Finding, id=fid)

    if request.method == 'POST':
        form = DeleteFindingForm(request.POST, instance=finding)
        if form.is_valid():
            tid = finding.test.id
            product = finding.test.engagement.product
            finding.delete()
            calculate_grade(product)
            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding deleted successfully.',
                extra_tags='alert-success')
            create_notification(event='other',
                                title='Deletion of %s' % finding.title,
                                description='The finding "%s" was deleted by %s' % (finding.title, request.user),
                                product=product,
                                url=request.build_absolute_uri(reverse('all_findings')),
                                recipients=[finding.test.engagement.lead],
                                icon="exclamation-triangle")
            return redirect_to_return_url_or_else(request, reverse('view_test', args=(tid,)))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'Unable to delete finding, please try again.',
                extra_tags='alert-danger')
    else:
        return HttpResponseForbidden()


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'change')
def edit_finding(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    # finding = finding._detag_to_serializable()
    # finding = finding._retag_to_original()
    old_status = finding.status()
    old_finding = copy.copy(finding)
    burp_rr = BurpRawRequestResponse.objects.filter(finding=finding).first()
    if burp_rr:
        req_resp = (
            burp_rr.get_request(),
            burp_rr.get_response()
        )
    else:
        req_resp = None
    form = FindingForm(instance=finding, template=False, req_resp=req_resp,
                       can_edit_mitigated_data=finding_helper.can_edit_mitigated_data(request.user))
    form_error = False
    jform = None
    push_all_jira_issues = jira_helper.is_push_all_issues(finding)
    gform = None
    use_jira = jira_helper.get_jira_project(finding) is not None

    github_enabled = finding.has_github_issue()

    if request.method == 'POST':
        form = FindingForm(request.POST, instance=finding, template=False, req_resp=None,
                           can_edit_mitigated_data=finding_helper.can_edit_mitigated_data(request.user))

        if finding.active:
            if (form['active'].value() is False or form['false_p'].value()) and form['duplicate'].value() is False:
                note_type_activation = Note_Type.objects.filter(is_active=True).count()
                closing_disabled = 0
                if note_type_activation:
                    closing_disabled = len(get_missing_mandatory_notetypes(finding))
                if closing_disabled != 0:
                    error_inactive = ValidationError('Can not set a finding as inactive without adding all mandatory notes',
                                                     code='inactive_without_mandatory_notes')
                    error_false_p = ValidationError('Can not set a finding as false positive without adding all mandatory notes',
                                                    code='false_p_without_mandatory_notes')
                    if form['active'].value() is False:
                        form.add_error('active', error_inactive)
                    if form['false_p'].value():
                        form.add_error('false_p', error_false_p)
                    messages.add_message(request,
                                         messages.ERROR,
                                         'Can not set a finding as inactive or false positive without adding all mandatory notes',
                                         extra_tags='alert-danger')

        if use_jira:
            jform = JIRAFindingForm(request.POST, prefix='jiraform', push_all=push_all_jira_issues, instance=finding, jira_project=jira_helper.get_jira_project(finding), finding_form=form)

        if form.is_valid() and (jform is None or jform.is_valid()):
            if jform:
                logger.debug('jform.jira_issue: %s', jform.cleaned_data.get('jira_issue'))
                logger.debug('jform.push_to_jira: %s', jform.cleaned_data.get('push_to_jira'))

            new_finding = form.save(commit=False)
            new_finding.test = finding.test
            new_finding.numerical_severity = Finding.get_numerical_severity(
                new_finding.severity)

            if 'group' in form.cleaned_data:
                finding_group = form.cleaned_data['group']
                finding_helper.update_finding_group(new_finding, finding_group)

            if 'risk_accepted' in form.cleaned_data and form['risk_accepted'].value():
                if new_finding.test.engagement.product.enable_simple_risk_acceptance:
                    ra_helper.simple_risk_accept(new_finding, perform_save=False)
            else:
                if new_finding.risk_accepted:
                    ra_helper.risk_unaccept(new_finding, perform_save=False)

            create_template = new_finding.is_template
            # always false now since this will be deprecated soon in favor of new Finding_Template model
            new_finding.is_template = False
            new_finding.endpoints.set(form.cleaned_data['endpoints'])
            for endpoint in form.cleaned_data['endpoints']:
                eps, created = Endpoint_Status.objects.get_or_create(
                    finding=new_finding,
                    endpoint=endpoint)
                endpoint.endpoint_status.add(eps)
                new_finding.endpoint_status.add(eps)
            new_finding.last_reviewed = timezone.now()
            new_finding.last_reviewed_by = request.user

            new_finding.tags = form.cleaned_data['tags']

            if 'request' in form.cleaned_data or 'response' in form.cleaned_data:
                burp_rr = BurpRawRequestResponse.objects.filter(finding=finding).first()
                if burp_rr:
                    burp_rr.burpRequestBase64 = base64.b64encode(form.cleaned_data['request'].encode())
                    burp_rr.burpResponseBase64 = base64.b64encode(form.cleaned_data['response'].encode())
                    burp_rr.clean()
                    burp_rr.save()

            push_to_jira = False
            jira_message = None
            if jform and jform.is_valid():
                # Push to Jira?

                logger.debug('jform.push_to_jira: %s', jform.cleaned_data.get('push_to_jira'))
                # can't use helper as when push_all_jira_issues is True, the checkbox gets disabled and is always false
                # push_to_jira = jira_helper.is_push_to_jira(new_finding, jform.cleaned_data.get('push_to_jira'))
                push_to_jira = push_all_jira_issues or jform.cleaned_data.get('push_to_jira')

                logger.debug('push_to_jira: %s', push_to_jira)
                logger.debug('push_all_jira_issues: %s', push_all_jira_issues)
                logger.debug('has_jira_group_issue: %s', new_finding.has_jira_group_issue)

                # if the jira issue key was changed, update database
                new_jira_issue_key = jform.cleaned_data.get('jira_issue')
                # we only support linking / changing if there is no group issue
                if not new_finding.has_jira_group_issue:
                    if new_finding.has_jira_issue:
                        jira_issue = new_finding.jira_issue

                        # everything in DD around JIRA integration is based on the internal id of the issue in JIRA
                        # instead of on the public jira issue key.
                        # I have no idea why, but it means we have to retrieve the issue from JIRA to get the internal JIRA id.
                        # we can assume the issue exist, which is already checked in the validation of the jform

                        if not new_jira_issue_key:
                            jira_helper.finding_unlink_jira(request, new_finding)
                            jira_message = 'Link to JIRA issue removed successfully.'

                        elif new_jira_issue_key != new_finding.jira_issue.jira_key:
                            jira_helper.finding_unlink_jira(request, new_finding)
                            jira_helper.finding_link_jira(request, new_finding, new_jira_issue_key)
                            jira_message = 'Changed JIRA link successfully.'
                    else:
                        if new_jira_issue_key:
                            jira_helper.finding_link_jira(request, new_finding, new_jira_issue_key)
                            jira_message = 'Linked a JIRA issue successfully.'

            if 'githubform-push_to_github' in request.POST:
                gform = GITHUBFindingForm(
                    request.POST, prefix='githubform', enabled=github_enabled)
                if gform.is_valid():
                    if GITHUB_Issue.objects.filter(finding=new_finding).exists():
                        update_external_issue(new_finding, old_status, 'github')
                    else:
                        add_external_issue(new_finding, 'github')

            # if there's a finding group, that's what we need to push
            push_group_to_jira = push_to_jira and new_finding.finding_group
            # any existing finding should be updated
            push_to_jira = push_to_jira and not push_group_to_jira and not new_finding.has_jira_issue

            # if we're removing the "duplicate" in the edit finding screen
            # do not relaunch deduplication, otherwise, it's never taken into account
            if old_finding.duplicate and not new_finding.duplicate:
                new_finding.duplicate_finding = None
                new_finding.save(push_to_jira=push_to_jira, dedupe_option=False)
            else:
                new_finding.save(push_to_jira=push_to_jira)

            # we only push the group after storing the finding to make sure
            # the updated data of the finding is pushed as part of the group
            if push_group_to_jira:
                jira_helper.push_to_jira(new_finding.finding_group)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding saved successfully.',
                extra_tags='alert-success')

            if jira_message:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    jira_message,
                    extra_tags='alert-success')

            if create_template:
                templates = Finding_Template.objects.filter(
                    title=new_finding.title)
                if len(templates) > 0:
                    messages.add_message(
                        request,
                        messages.ERROR,
                        'A finding template was not created.  A template with this title already '
                        'exists.',
                        extra_tags='alert-danger')
                else:
                    template = Finding_Template(
                        title=new_finding.title,
                        cwe=new_finding.cwe,
                        severity=new_finding.severity,
                        description=new_finding.description,
                        mitigation=new_finding.mitigation,
                        impact=new_finding.impact,
                        references=new_finding.references,
                        numerical_severity=new_finding.numerical_severity)
                    template.save()
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        'A finding template was also created.',
                        extra_tags='alert-success')

            return redirect_to_return_url_or_else(request, reverse('view_finding', args=(new_finding.id,)))
        else:
            add_error_message_to_response('The form has errors, please correct them below.')
            add_field_errors_to_response(jform)
            add_field_errors_to_response(form)
            form_error = True
    else:
        if use_jira:
            jform = JIRAFindingForm(push_all=push_all_jira_issues, prefix='jiraform', instance=finding, jira_project=jira_helper.get_jira_project(finding), finding_form=form)

        if get_system_setting('enable_github'):
            if GITHUB_PKey.objects.filter(product=finding.test.engagement.product).exclude(git_conf_id=None):
                gform = GITHUBFindingForm(enabled=github_enabled, prefix='githubform')

    if form_error and 'endpoints' in form.cleaned_data:
        form.fields['endpoints'].queryset = form.cleaned_data['endpoints']
    else:
        form.fields['endpoints'].queryset = finding.endpoints.all()

    product_tab = Product_Tab(finding.test.engagement.product.id, title="Edit Finding", tab="findings")

    return render(request, 'dojo/edit_finding.html', {
        'product_tab': product_tab,
        'form': form,
        'finding': finding,
        'jform': jform,
        'gform': gform,
        'return_url': get_return_url(request)
    })


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'change')
def touch_finding(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    finding.last_reviewed = timezone.now()
    finding.last_reviewed_by = request.user
    finding.save()
    return redirect_to_return_url_or_else(request, reverse('view_finding', args=(finding.id, )))


@user_is_authorized(Finding, Permissions.Risk_Acceptance, 'fid', 'staff')
def simple_risk_accept(request, fid):
    finding = get_object_or_404(Finding, id=fid)

    if not finding.test.engagement.product.enable_simple_risk_acceptance:
        raise PermissionDenied()

    ra_helper.simple_risk_accept(finding)

    return redirect_to_return_url_or_else(request, reverse('view_finding', args=(finding.id, )))


@user_is_authorized(Finding, Permissions.Risk_Acceptance, 'fid', 'staff')
def risk_unaccept(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    ra_helper.risk_unaccept(finding)
    return redirect_to_return_url_or_else(request, reverse('view_finding', args=(finding.id, )))


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'staff')
def request_finding_review(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    user = get_object_or_404(Dojo_User, id=request.user.id)
    # in order to review a finding, we need to capture why a review is needed
    # we can do this with a Note
    if request.method == 'POST':
        form = ReviewFindingForm(request.POST)

        if form.is_valid():
            now = timezone.now()
            new_note = Notes()
            new_note.entry = "Review Request: " + form.cleaned_data['entry']
            new_note.private = True
            new_note.author = request.user
            new_note.date = now
            new_note.save()
            finding.notes.add(new_note)
            finding.active = False
            finding.verified = False
            finding.is_mitigated = False
            finding.under_review = True
            finding.review_requested_by = user
            finding.last_reviewed = now
            finding.last_reviewed_by = request.user

            users = form.cleaned_data['reviewers']
            finding.reviewers.set(users)
            finding.save()
            reviewers = ""
            for suser in form.cleaned_data['reviewers']:
                reviewers += str(suser) + ", "
            reviewers = reviewers[:-2]

            create_notification(event='review_requested',
                                title='Finding review requested',
                                finding=finding,
                                description='User %s has requested that users %s review the finding "%s" for accuracy:\n\n%s' % (user, reviewers, finding.title, new_note),
                                icon='check',
                                url=reverse("view_finding", args=(finding.id,)))

            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding marked for review and reviewers notified.',
                extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('view_finding', args=(finding.id, )))

    else:
        form = ReviewFindingForm()

    product_tab = Product_Tab(finding.test.engagement.product.id, title="Review Finding", tab="findings")

    return render(request, 'dojo/review_finding.html', {
        'finding': finding,
        'product_tab': product_tab,
        'user': user,
        'form': form
    })


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'staff')
def clear_finding_review(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    user = get_object_or_404(Dojo_User, id=request.user.id)
    # in order to clear a review for a finding, we need to capture why and how it was reviewed
    # we can do this with a Note

    if user == finding.review_requested_by or user in finding.reviewers.all():
        pass
    else:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = ClearFindingReviewForm(request.POST, instance=finding)

        if form.is_valid():
            now = timezone.now()
            new_note = Notes()
            new_note.entry = "Review Cleared: " + form.cleaned_data['entry']
            new_note.author = request.user
            new_note.date = now
            new_note.save()

            finding = form.save(commit=False)

            finding.under_review = False
            finding.last_reviewed = now
            finding.last_reviewed_by = request.user

            finding.reviewers.set([])
            finding.save()

            finding.notes.add(new_note)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding review has been updated successfully.',
                extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('view_finding', args=(finding.id, )))

    else:
        form = ClearFindingReviewForm(instance=finding)

    product_tab = Product_Tab(finding.test.engagement.product.id, title="Clear Finding Review", tab="findings")

    return render(request, 'dojo/clear_finding_review.html', {
        'finding': finding,
        'product_tab': product_tab,
        'user': user,
        'form': form
    })


@user_passes_test(lambda u: u.is_staff)
def mktemplate(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    templates = Finding_Template.objects.filter(title=finding.title)
    if len(templates) > 0:
        messages.add_message(
            request,
            messages.ERROR,
            'A finding template with that title already exists.',
            extra_tags='alert-danger')
    else:
        template = Finding_Template(
            title=finding.title,
            cwe=finding.cwe,
            cve=finding.cve,
            cvssv3=finding.cvssv3,
            severity=finding.severity,
            description=finding.description,
            mitigation=finding.mitigation,
            impact=finding.impact,
            references=finding.references,
            numerical_severity=finding.numerical_severity,
            tags=finding.tags.all())
        template.save()
        template.tags = finding.tags.all()

        messages.add_message(
            request,
            messages.SUCCESS,
            mark_safe(
                'Finding template added successfully. You may edit it <a href="%s">here</a>.'
                % reverse('edit_template', args=(template.id, ))),
            extra_tags='alert-success')
    return HttpResponseRedirect(reverse('view_finding', args=(finding.id, )))


@user_passes_test(lambda u: u.is_staff)
def find_template_to_apply(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    test = get_object_or_404(Test, id=finding.test.id)
    templates_by_CVE = Finding_Template.objects.annotate(
                                            cve_len=Length('cve'), order=models.Value(1, models.IntegerField())).filter(
                                                cve=finding.cve, cve_len__gt=0).order_by('-last_used')
    if templates_by_CVE.count() == 0:

        templates_by_last_used = Finding_Template.objects.all().order_by(
                                                '-last_used').annotate(
                                                    cve_len=Length('cve'), order=models.Value(2, models.IntegerField()))
        templates = templates_by_last_used
    else:
        templates_by_last_used = Finding_Template.objects.all().exclude(
                                                cve=finding.cve).order_by(
                                                    '-last_used').annotate(
                                                        cve_len=Length('cve'), order=models.Value(2, models.IntegerField()))
        templates = templates_by_last_used.union(templates_by_CVE).order_by('order', '-last_used')

    templates = TemplateFindingFilter(request.GET, queryset=templates)
    paged_templates = get_page_items(request, templates.qs, 25)

    # just query all templates as this weird ordering above otherwise breaks Django ORM
    title_words = get_words_for_field(Finding_Template, 'title')
    product_tab = Product_Tab(test.engagement.product.id, title="Apply Template to Finding", tab="findings")
    return render(
        request, 'dojo/templates.html', {
            'templates': paged_templates,
            'product_tab': product_tab,
            'filtered': templates,
            'title_words': title_words,
            'tid': test.id,
            'fid': fid,
            'add_from_template': False,
            'apply_template': True,
        })


@user_passes_test(lambda u: u.is_staff)
def choose_finding_template_options(request, tid, fid):
    finding = get_object_or_404(Finding, id=fid)
    template = get_object_or_404(Finding_Template, id=tid)
    data = finding.__dict__
    # Not sure what's going on here, just leave same as with django-tagging
    data['tags'] = [tag.name for tag in template.tags.all()]
    form = ApplyFindingTemplateForm(data=data, template=template)
    product_tab = Product_Tab(finding.test.engagement.product.id, title="Finding Template Options", tab="findings")
    return render(request, 'dojo/apply_finding_template.html', {
        'finding': finding,
        'product_tab': product_tab,
        'template': template,
        'form': form,
        'finding_tags': [tag.name for tag in finding.tags.all()],
    })


@user_passes_test(lambda u: u.is_staff)
def apply_template_to_finding(request, fid, tid):
    finding = get_object_or_404(Finding, id=fid)
    template = get_object_or_404(Finding_Template, id=tid)

    if (request.method == "POST"):
        form = ApplyFindingTemplateForm(data=request.POST)

        if form.is_valid():
            template.last_used = timezone.now()
            template.save()
            finding.title = form.cleaned_data['title']
            finding.cwe = form.cleaned_data['cwe']
            finding.cve = form.cleaned_data['cve']
            finding.severity = form.cleaned_data['severity']
            finding.description = form.cleaned_data['description']
            finding.mitigation = form.cleaned_data['mitigation']
            finding.impact = form.cleaned_data['impact']
            finding.references = form.cleaned_data['references']
            finding.last_reviewed = timezone.now()
            finding.last_reviewed_by = request.user
            finding.tags = form.cleaned_data['tags']
            finding.save()
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'There appears to be errors on the form, please correct below.',
                extra_tags='alert-danger')
            # form_error = True
            product_tab = Product_Tab(finding.test.engagement.product.id, title="Apply Finding Template", tab="findings")
            return render(request, 'dojo/apply_finding_template.html', {
                'finding': finding,
                'product_tab': product_tab,
                'template': template,
                'form': form,
            })

        return HttpResponseRedirect(
            reverse('view_finding', args=(finding.id, )))
    else:
        return HttpResponseRedirect(
            reverse('view_finding', args=(finding.id, )))


@user_is_authorized(Finding, Permissions.Finding_Add, 'tid', 'staff')
def add_stub_finding(request, tid):
    test = get_object_or_404(Test, id=tid)
    form = StubFindingForm()
    if request.method == 'POST':
        form = StubFindingForm(request.POST)
        if form.is_valid():
            stub_finding = form.save(commit=False)
            stub_finding.test = test
            stub_finding.reporter = request.user
            stub_finding.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                'Stub Finding created successfully.',
                extra_tags='alert-success')
            if request.is_ajax():
                data = {
                    'message': 'Stub Finding created successfully.',
                    'id': stub_finding.id,
                    'severity': 'None',
                    'date': formats.date_format(stub_finding.date,
                                                "DATE_FORMAT")
                }
                return HttpResponse(json.dumps(data))
        else:
            if request.is_ajax():
                data = {
                    'message':
                    'Stub Finding form has error, please revise and try again.',
                }
                return HttpResponse(json.dumps(data))

            messages.add_message(
                request,
                messages.ERROR,
                'Stub Finding form has error, please revise and try again.',
                extra_tags='alert-danger')
    add_breadcrumb(title="Add Stub Finding", top_level=False, request=request)
    return HttpResponseRedirect(reverse('view_test', args=(tid, )))


@user_is_authorized(Finding, Permissions.Finding_Delete, 'fid', 'staff')
def delete_stub_finding(request, fid):
    finding = get_object_or_404(Stub_Finding, id=fid)
    form = DeleteStubFindingForm(instance=finding)

    if request.method == 'POST':
        form = DeleteStubFindingForm(request.POST, instance=finding)
        if form.is_valid():
            tid = finding.test.id
            finding.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                'Potential Finding deleted successfully.',
                extra_tags='alert-success')
            return HttpResponseRedirect(reverse('view_test', args=(tid, )))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'Unable to delete potential finding, please try again.',
                extra_tags='alert-danger')
    else:
        return HttpResponseForbidden()


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'staff')
def promote_to_finding(request, fid):
    finding = get_object_or_404(Stub_Finding, id=fid)
    test = finding.test
    form_error = False
    jira_available = False
    push_all_jira_issues = jira_helper.is_push_all_issues(finding)
    jform = None
    use_jira = jira_helper.get_jira_project(finding) is not None
    product_tab = Product_Tab(finding.test.engagement.product.id, title="Promote Finding", tab="findings")

    if request.method == 'POST':
        form = PromoteFindingForm(request.POST)
        if use_jira:
            jform = JIRAFindingForm(request.POST, instance=finding, prefix='jiraform', push_all=push_all_jira_issues, jira_project=jira_helper.get_jira_project(finding))

        if form.is_valid() and (jform is None or jform.is_valid()):
            if jform:
                logger.debug('jform.jira_issue: %s', jform.cleaned_data.get('jira_issue'))
                logger.debug('jform.push_to_jira: %s', jform.cleaned_data.get('push_to_jira'))

            new_finding = form.save(commit=False)
            new_finding.test = test
            new_finding.reporter = request.user
            new_finding.numerical_severity = Finding.get_numerical_severity(
                new_finding.severity)

            new_finding.active = True
            new_finding.false_p = False
            new_finding.duplicate = False
            new_finding.mitigated = None
            new_finding.verified = True
            new_finding.out_of_scope = False

            new_finding.save()
            new_finding.endpoints.set(form.cleaned_data['endpoints'])

            # Push to jira?
            push_to_jira = False
            jira_message = None
            if jform and jform.is_valid():
                # Push to Jira?
                logger.debug('jira form valid')
                push_to_jira = push_all_jira_issues or jform.cleaned_data.get('push_to_jira')

                # if the jira issue key was changed, update database
                new_jira_issue_key = jform.cleaned_data.get('jira_issue')
                if new_finding.has_jira_issue:
                    jira_issue = new_finding.jira_issue

                    # everything in DD around JIRA integration is based on the internal id of the issue in JIRA
                    # instead of on the public jira issue key.
                    # I have no idea why, but it means we have to retrieve the issue from JIRA to get the internal JIRA id.
                    # we can assume the issue exist, which is already checked in the validation of the jform

                    if not new_jira_issue_key:
                        jira_helper.finding_unlink_jira(request, new_finding)
                        jira_message = 'Link to JIRA issue removed successfully.'

                    elif new_jira_issue_key != new_finding.jira_issue.jira_key:
                        jira_helper.finding_unlink_jira(request, new_finding)
                        jira_helper.finding_link_jira(request, new_finding, new_jira_issue_key)
                        jira_message = 'Changed JIRA link successfully.'
                else:
                    logger.debug('finding has no jira issue yet')
                    if new_jira_issue_key:
                        logger.debug('finding has no jira issue yet, but jira issue specified in request. trying to link.')
                        jira_helper.finding_link_jira(request, new_finding, new_jira_issue_key)
                        jira_message = 'Linked a JIRA issue successfully.'

            # Save it and push it to JIRA
            new_finding.save(push_to_jira=push_to_jira)

            # Delete potential finding
            finding.delete()
            if 'githubform' in request.POST:
                gform = GITHUBFindingForm(
                    request.POST,
                    prefix='githubform',
                    enabled=GITHUB_PKey.objects.get(
                        product=test.engagement.product).push_all_issues)
                if gform.is_valid():
                    add_external_issue(new_finding, 'github')

            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding promoted successfully.',
                extra_tags='alert-success')

            return HttpResponseRedirect(reverse('view_test', args=(test.id, )))
        else:
            if 'endpoints' in form.cleaned_data:
                form.fields['endpoints'].queryset = form.cleaned_data[
                    'endpoints']
            else:
                form.fields['endpoints'].queryset = Endpoint.objects.none()
            form_error = True
            add_error_message_to_response('The form has errors, please correct them below.')
            add_field_errors_to_response(jform)
            add_field_errors_to_response(form)
    else:

        form = PromoteFindingForm(
            initial={
                'title': finding.title,
                'product_tab': product_tab,
                'date': finding.date,
                'severity': finding.severity,
                'description': finding.description,
                'test': finding.test,
                'reporter': finding.reporter
            })

        if use_jira:
            jform = JIRAFindingForm(prefix='jiraform', push_all=jira_helper.is_push_all_issues(test), jira_project=jira_helper.get_jira_project(test))

    return render(
        request, 'dojo/promote_to_finding.html', {
            'form': form,
            'product_tab': product_tab,
            'test': test,
            'stub_finding': finding,
            'form_error': form_error,
            'jform': jform,
        })


@user_passes_test(lambda u: u.is_staff)
def templates(request):
    templates = Finding_Template.objects.all().order_by('cwe')
    templates = TemplateFindingFilter(request.GET, queryset=templates)
    paged_templates = get_page_items(request, templates.qs, 25)

    title_words = get_words_for_field(templates.qs, 'title')

    add_breadcrumb(title="Template Listing", top_level=True, request=request)
    return render(
        request, 'dojo/templates.html', {
            'templates': paged_templates,
            'filtered': templates,
            'title_words': title_words,

        })


@user_passes_test(lambda u: u.is_staff)
def export_templates_to_json(request):
    leads_as_json = serializers.serialize('json', Finding_Template.objects.all())
    return HttpResponse(leads_as_json, content_type='json')


def apply_cwe_mitigation(apply_to_findings, template, update=True):
    count = 0
    if apply_to_findings and template.template_match and template.cwe is not None:
        # Update active, verified findings with the CWE template
        # If CWE only match only update issues where there isn't a CWE + Title match
        if template.template_match_title:
            count = Finding.objects.filter(active=True, verified=True, cwe=template.cwe, title__icontains=template.title).update(mitigation=template.mitigation, impact=template.impact, references=template.references)
        else:
            finding_templates = Finding_Template.objects.filter(cwe=template.cwe, template_match=True, template_match_title=True)

            finding_ids = None
            result_list = None
            # Exclusion list
            for title_template in finding_templates:
                finding_ids = Finding.objects.filter(active=True, verified=True, cwe=title_template.cwe, title__icontains=title_template.title).values_list('id', flat=True)
                if result_list is None:
                    result_list = finding_ids
                else:
                    result_list = list(chain(result_list, finding_ids))

            # If result_list is None the filter exclude won't work
            if result_list:
                count = Finding.objects.filter(active=True, verified=True, cwe=template.cwe).exclude(id__in=result_list)
            else:
                count = Finding.objects.filter(active=True, verified=True, cwe=template.cwe)

            if update:
                # MySQL won't allow an 'update in statement' so loop will have to do
                for finding in count:
                    finding.mitigation = template.mitigation
                    finding.impact = template.impact
                    finding.references = template.references
                    template.last_used = timezone.now()
                    template.save()
                    new_note = Notes()
                    new_note.entry = 'CWE remediation text applied to finding for CWE: %s using template: %s.' % (template.cwe, template.title)
                    new_note.author, created = User.objects.get_or_create(username='System')
                    new_note.save()
                    finding.notes.add(new_note)
                    finding.save()

            count = count.count()
    return count


@user_passes_test(lambda u: u.is_staff)
def add_template(request):
    form = FindingTemplateForm()
    if request.method == 'POST':
        form = FindingTemplateForm(request.POST)
        if form.is_valid():
            apply_message = ""
            template = form.save(commit=False)
            template.numerical_severity = Finding.get_numerical_severity(template.severity)
            template.save()
            form.save_m2m()
            count = apply_cwe_mitigation(form.cleaned_data["apply_to_findings"], template)
            if count > 0:
                apply_message = " and " + str(count) + pluralize(count, 'finding,findings') + " "

            messages.add_message(
                request,
                messages.SUCCESS,
                'Template created successfully. ' + apply_message,
                extra_tags='alert-success')
            return HttpResponseRedirect(reverse('templates'))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'Template form has error, please revise and try again.',
                extra_tags='alert-danger')
    add_breadcrumb(title="Add Template", top_level=False, request=request)
    return render(request, 'dojo/add_template.html', {
        'form': form,
        'name': 'Add Template'
    })


@user_passes_test(lambda u: u.is_staff)
def edit_template(request, tid):
    template = get_object_or_404(Finding_Template, id=tid)
    form = FindingTemplateForm(instance=template)

    if request.method == 'POST':
        form = FindingTemplateForm(request.POST, instance=template)
        if form.is_valid():
            template = form.save(commit=False)
            template.numerical_severity = Finding.get_numerical_severity(template.severity)
            template.save()
            form.save_m2m()

            count = apply_cwe_mitigation(form.cleaned_data["apply_to_findings"], template)
            if count > 0:
                apply_message = " and " + str(count) + " " + pluralize(count, 'finding,findings') + " "
            else:
                apply_message = ""

            messages.add_message(
                request,
                messages.SUCCESS,
                'Template ' + apply_message + 'updated successfully.',
                extra_tags='alert-success')
            return HttpResponseRedirect(reverse('templates'))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'Template form has error, please revise and try again.',
                extra_tags='alert-danger')

    count = apply_cwe_mitigation(True, template, False)
    add_breadcrumb(title="Edit Template", top_level=False, request=request)
    return render(request, 'dojo/add_template.html', {
        'form': form,
        'count': count,
        'name': 'Edit Template',
        'template': template,
    })


@user_passes_test(lambda u: u.is_staff)
def delete_template(request, tid):
    template = get_object_or_404(Finding_Template, id=tid)

    form = DeleteFindingTemplateForm(instance=template)

    if request.method == 'POST':
        form = DeleteFindingTemplateForm(request.POST, instance=template)
        if form.is_valid():
            template.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding Template deleted successfully.',
                extra_tags='alert-success')
            return HttpResponseRedirect(reverse('templates'))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                'Unable to delete Template, please revise and try again.',
                extra_tags='alert-danger')
    else:
        return HttpResponseForbidden()


def download_finding_pic(request, token):
    class Thumbnail(ImageSpec):
        processors = [ResizeToFill(100, 100)]
        format = 'JPEG'
        options = {'quality': 70}

    class Small(ImageSpec):
        processors = [ResizeToFill(640, 480)]
        format = 'JPEG'
        options = {'quality': 100}

    class Medium(ImageSpec):
        processors = [ResizeToFill(800, 600)]
        format = 'JPEG'
        options = {'quality': 100}

    class Large(ImageSpec):
        processors = [ResizeToFill(1024, 768)]
        format = 'JPEG'
        options = {'quality': 100}

    class Original(ImageSpec):
        format = 'JPEG'
        options = {'quality': 100}

    mimetypes.init()

    size_map = {
        'thumbnail': Thumbnail,
        'small': Small,
        'medium': Medium,
        'large': Large,
        'original': Original,
    }

    try:
        access_token = FileAccessToken.objects.get(token=token)
        size = access_token.size

        if access_token.size not in list(size_map.keys()):
            raise Http404
        size = access_token.size
        # we know there is a token - is it for this image
        if access_token.size == size:
            ''' all is good, one time token used, delete it '''
            access_token.delete()
        else:
            raise PermissionDenied
    except:
        raise PermissionDenied

    with open(access_token.file.file.file.name, 'rb') as file:
        file_name = file.name
        image = size_map[size](source=file).generate()
        response = StreamingHttpResponse(FileIterWrapper(image))
        response['Content-Disposition'] = 'inline'
        mimetype, encoding = mimetypes.guess_type(file_name)
        response['Content-Type'] = mimetype
        return response


@user_is_authorized(Product, Permissions.Finding_Edit, 'pid', 'staff')
def merge_finding_product(request, pid):
    product = get_object_or_404(Product, pk=pid)
    finding_to_update = request.GET.getlist('finding_to_update')
    findings = None

    if (request.GET.get('merge_findings') or request.method == 'POST') and finding_to_update:
        finding = Finding.objects.get(id=finding_to_update[0], test__engagement__product=product)
        findings = Finding.objects.filter(id__in=finding_to_update, test__engagement__product=product)
        form = MergeFindings(finding=finding, findings=findings, initial={'finding_to_merge_into': finding_to_update[0]})

        if request.method == 'POST':
            form = MergeFindings(request.POST, finding=finding, findings=findings)
            if form.is_valid():
                finding_to_merge_into = form.cleaned_data['finding_to_merge_into']
                findings_to_merge = form.cleaned_data['findings_to_merge']
                finding_descriptions = ''
                finding_references = ''
                notes_entry = ''
                static = False
                dynamic = False

                if finding_to_merge_into not in findings_to_merge:
                    for finding in findings_to_merge.exclude(pk=finding_to_merge_into.pk):
                        notes_entry = "{} {} ({}),".format(notes_entry, finding.title, finding.id)
                        if finding.static_finding:
                            static = finding.static_finding

                        if finding.dynamic_finding:
                            dynamic = finding.dynamic_finding

                        if finding.line:
                            line = finding.line

                        if finding.file_path:
                            file_path = finding.file_path

                        # If checked merge the descriptions
                        if form.cleaned_data['append_description']:
                            finding_descriptions = "{}\n{}".format(finding_descriptions, finding.description)
                            # Workaround until file path is one to many
                            if finding.file_path:
                                finding_descriptions = "{}\n**File Path:** {}\n".format(finding_descriptions, finding.file_path)

                        # If checked merge the Reference
                        if form.cleaned_data['append_reference']:
                            finding_references = "{}\n{}".format(finding_references, finding.references)

                        # if checked merge the endpoints
                        if form.cleaned_data['add_endpoints']:
                            finding_to_merge_into.endpoints.add(*finding.endpoints.all())

                        # if checked merge the tags
                        if form.cleaned_data['tag_finding']:
                            for tag in finding.tags.all():
                                finding_to_merge_into.tags.add(tag)

                        # if checked re-assign the burp requests to the merged finding
                        if form.cleaned_data['dynamic_raw']:
                            BurpRawRequestResponse.objects.filter(finding=finding).update(finding=finding_to_merge_into)

                        # Add merge finding information to the note if set to inactive
                        if form.cleaned_data['finding_action'] == "inactive":
                            single_finding_notes_entry = "Finding has been set to inactive and merged with the finding: {}.".format(finding_to_merge_into.title)
                            note = Notes(entry=single_finding_notes_entry, author=request.user)
                            note.save()
                            finding.notes.add(note)

                            # If the merged finding should be tagged as merged-into
                            if form.cleaned_data['mark_tag_finding']:
                                finding.tags.add("merged-inactive")

                    # Update the finding to merge into
                    if finding_descriptions != '':
                        finding_to_merge_into.description = "{}\n\n{}".format(finding_to_merge_into.description, finding_descriptions)

                    if finding_to_merge_into.static_finding:
                        static = finding.static_finding

                    if finding_to_merge_into.dynamic_finding:
                        dynamic = finding.dynamic_finding

                    if finding_to_merge_into.line is None:
                        line = finding_to_merge_into.line

                    if finding_to_merge_into.file_path is None:
                        file_path = finding_to_merge_into.file_path

                    if finding_references != '':
                        finding_to_merge_into.references = "{}\n{}".format(finding_to_merge_into.references, finding_references)

                    finding_to_merge_into.static_finding = static
                    finding_to_merge_into.dynamic_finding = dynamic

                    # Update the timestamp
                    finding_to_merge_into.last_reviewed = timezone.now()
                    finding_to_merge_into.last_reviewed_by = request.user

                    # Save the data to the merged finding
                    finding_to_merge_into.save()

                    # If the finding merged into should be tagged as merged
                    if form.cleaned_data['mark_tag_finding']:
                        finding_to_merge_into.tags.add("merged")

                    finding_action = ""
                    # Take action on the findings
                    if form.cleaned_data['finding_action'] == "inactive":
                        finding_action = "inactivated"
                        findings_to_merge.exclude(pk=finding_to_merge_into.pk).update(active=False, last_reviewed=timezone.now(), last_reviewed_by=request.user)
                    elif form.cleaned_data['finding_action'] == "delete":
                        finding_action = "deleted"
                        findings_to_merge.delete()

                    notes_entry = "Finding consists of merged findings from the following findings: {} which have been {}.".format(notes_entry[:-1], finding_action)
                    note = Notes(entry=notes_entry, author=request.user)
                    note.save()
                    finding_to_merge_into.notes.add(note)

                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        'Findings merged',
                        extra_tags='alert-success')
                    return HttpResponseRedirect(
                        reverse('edit_finding', args=(finding_to_merge_into.id, )))
                else:
                    messages.add_message(request,
                                         messages.ERROR,
                                         'Unable to merge findings. Findings to merge contained in finding to merge into.',
                                         extra_tags='alert-danger')
            else:
                messages.add_message(request,
                                     messages.ERROR,
                                     'Unable to merge findings. Required fields were not selected.',
                                     extra_tags='alert-danger')

    product_tab = Product_Tab(finding.test.engagement.product.id, title="Merge Findings", tab="findings")
    custom_breadcrumb = {"Open Findings": reverse('product_open_findings', args=(finding.test.engagement.product.id, )) + '?test__engagement__product=' + str(finding.test.engagement.product.id)}

    return render(request, 'dojo/merge_findings.html', {
        'form': form,
        'name': 'Merge Findings',
        'finding': finding,
        'product_tab': product_tab,
        'title': product_tab.title,
        'custom_breadcrumb': custom_breadcrumb
    })


# bulk update and delete are combined, so we can't have the nice user_is_authorized decorator
def finding_bulk_update_all(request, pid=None):
    logger.debug('bulk 10')
    form = FindingBulkUpdateForm(request.POST)
    now = timezone.now()
    return_url = None

    if request.method == "POST":
        logger.debug('bulk 20')

        finding_to_update = request.POST.getlist('finding_to_update')
        finds = Finding.objects.filter(id__in=finding_to_update).order_by("id")
        total_find_count = finds.count()
        skipped_find_count = 0
        prods = set([find.test.engagement.product for find in finds])
        if request.POST.get('delete_bulk_findings'):
            if form.is_valid() and finding_to_update:

                if not settings.FEATURE_AUTHORIZATION_V2:
                    if not request.user.is_staff and not settings.AUTHORIZED_USERS_ALLOW_DELETE and not settings.AUTHORIZED_USERS_ALLOW_STAFF:
                        raise PermissionDenied
                else:
                    if pid is None:
                        if not request.user.is_staff:
                            raise PermissionDenied
                    else:
                        product = get_object_or_404(Product, id=pid)
                        user_has_permission_or_403(request.user, product, Permissions.Finding_Delete)

                finds = get_authorized_findings(Permissions.Finding_Delete, finds).distinct()

                skipped_find_count = total_find_count - finds.count()
                deleted_find_count = finds.count()

                for find in finds:
                    find.delete()

                # for prod in prods:
                #     calculate_grade(prod)

                if skipped_find_count > 0:
                    add_error_message_to_response('Skipped deletion of {} findings because you are not authorized.'.format(skipped_find_count))

                if deleted_find_count > 0:
                    messages.add_message(request,
                        messages.SUCCESS,
                        'Bulk delete of {} findings was successful.'.format(deleted_find_count),
                        extra_tags='alert-success')
        else:
            if form.is_valid() and finding_to_update:

                if not settings.FEATURE_AUTHORIZATION_V2:
                    if not request.user.is_staff and not settings.AUTHORIZED_USERS_ALLOW_CHANGE and not settings.AUTHORIZED_USERS_ALLOW_STAFF:
                        raise PermissionDenied
                else:
                    if pid is None:
                        if not request.user.is_staff:
                            raise PermissionDenied
                    else:
                        product = get_object_or_404(Product, id=pid)
                        user_has_permission_or_403(request.user, product, Permissions.Finding_Edit)

                # make sure users are not editing stuff they are not authorized for
                finds = get_authorized_findings(Permissions.Finding_Edit, finds).distinct()

                skipped_find_count = total_find_count - finds.count()
                updated_find_count = finds.count()

                if skipped_find_count > 0:
                    add_error_message_to_response('Skipped update of {} findings because you are not authorized.'.format(skipped_find_count))

                finds = prefetch_for_findings(finds)
                if form.cleaned_data['severity'] or form.cleaned_data['status']:
                    for find in finds:
                        if form.cleaned_data['severity']:
                            find.severity = form.cleaned_data['severity']
                            find.numerical_severity = Finding.get_numerical_severity(form.cleaned_data['severity'])
                            find.last_reviewed = now
                            find.last_reviewed_by = request.user

                        if form.cleaned_data['status']:
                            # logger.debug('setting status from bulk edit form: %s', form)
                            find.active = form.cleaned_data['active']
                            find.verified = form.cleaned_data['verified']
                            find.false_p = form.cleaned_data['false_p']
                            find.out_of_scope = form.cleaned_data['out_of_scope']
                            find.is_mitigated = form.cleaned_data['is_mitigated']
                            find.last_reviewed = timezone.now()
                            find.last_reviewed_by = request.user

                        # use super to avoid all custom logic in our overriden save method
                        # it will trigger the pre_save signal
                        find.save_no_options()

                    for prod in prods:
                        calculate_grade(prod)

                skipped_risk_accept_count = 0
                if form.cleaned_data['risk_acceptance']:
                    for finding in finds:
                        if form.cleaned_data['risk_accept']:
                            if not finding.test.engagement.product.enable_simple_risk_acceptance:
                                skipped_risk_accept_count += 1
                            else:
                                ra_helper.simple_risk_accept(finding)
                        elif form.cleaned_data['risk_unaccept']:
                            ra_helper.risk_unaccept(finding)

                    for prod in prods:
                        calculate_grade(prod)

                if skipped_risk_accept_count > 0:
                    messages.add_message(request,
                                        messages.WARNING,
                                        'Skipped simple risk acceptance of %i findings, simple risk acceptance is disabled on the related products' % skipped_risk_accept_count,
                                        extra_tags='alert-warning')

                if form.cleaned_data['finding_group_create']:
                    logger.debug('finding_group_create checked!')
                    finding_group_name = form.cleaned_data['finding_group_create_name']
                    logger.debug('finding_group_create_name: %s', finding_group_name)
                    finding_group, added, skipped = finding_helper.create_finding_group(finds, finding_group_name)

                    if added:
                        add_success_message_to_response('Created finding group with %s findings' % added)
                        return_url = reverse('view_finding_group', args=(finding_group.id,))

                    if skipped:
                        add_success_message_to_response('Skipped %s findings in group creation, findings already part of another group' % skipped)

                    # refresh findings from db
                    finds = finds.all()

                if form.cleaned_data['finding_group_add']:
                    logger.debug('finding_group_add checked!')
                    fgid = form.cleaned_data['add_to_finding_group']
                    finding_group = Finding_Group.objects.get(id=fgid)
                    finding_group, added, skipped = finding_helper.add_to_finding_group(finding_group, finds)

                    if added:
                        add_success_message_to_response('Added %s findings to finding group %s' % (added, finding_group.name))
                        return_url = reverse('view_finding_group', args=(finding_group.id,))

                    if skipped:
                        add_success_message_to_response('Skipped %s findings when adding to finding group %s, findings already part of another group' % (skipped, finding_group.name))

                    # refresh findings from db
                    finds = finds.all()

                if form.cleaned_data['finding_group_remove']:
                    logger.debug('finding_group_remove checked!')
                    finding_groups, removed, skipped = finding_helper.remove_from_finding_group(finds)

                    if removed:
                        add_success_message_to_response('Removed %s findings from finding groups %s' % (removed, ','.join([finding_group.name for finding_group in finding_groups])))

                    if skipped:
                        add_success_message_to_response('Skipped %s findings when removing from any finding group, findings not part of any group' % (skipped))

                    # refresh findings from db
                    finds = finds.all()

                if form.cleaned_data['finding_group_by']:
                    logger.debug('finding_group_by checked!')
                    logger.debug(form.cleaned_data)
                    finding_group_by_option = form.cleaned_data['finding_group_by_option']
                    logger.debug('finding_group_by_option: %s', finding_group_by_option)

                    finding_groups, grouped, skipped, groups_created = finding_helper.group_findings_by(finds, finding_group_by_option)

                    if grouped:
                        add_success_message_to_response('Grouped %d findings into %d (%d newly created) finding groups' % (grouped, len(finding_groups), groups_created))

                    if skipped:
                        add_success_message_to_response('Skipped %s findings when grouping by %s as these findings were already in an existing group' % (skipped, finding_group_by_option))

                    # refresh findings from db
                    finds = finds.all()

                if form.cleaned_data['push_to_github']:
                    logger.info('push selected findings to github')
                    for finding in finds:
                        logger.debug('will push to GitHub finding: ' + str(finding))
                        old_status = finding.status()
                        if form.cleaned_data['push_to_github']:
                            if GITHUB_Issue.objects.filter(finding=finding).exists():
                                update_external_issue(finding, old_status, 'github')
                            else:
                                add_external_issue(finding, 'github')

                if form.cleaned_data['tags']:
                    for finding in finds:
                        # tags = tagulous.utils.render_tags(form.cleaned_data['tags'])
                        tags = form.cleaned_data['tags']
                        logger.debug('bulk_edit: setting tags for: %i %s %s', finding.id, finding, tags)
                        # currently bulk edit overwrites existing tags
                        finding.tags = tags
                        finding.save()

                error_counts = defaultdict(lambda: 0)
                success_count = 0
                finding_groups = set([find.finding_group for find in finds if find.has_finding_group])
                logger.info('finding_groups: %s', finding_groups)
                for group in finding_groups:
                    if form.cleaned_data.get('push_to_jira'):
                        can_be_pushed_to_jira, error_message, error_code = jira_helper.can_be_pushed_to_jira(group)
                        if not can_be_pushed_to_jira:
                            error_counts[error_message] += 1
                            jira_helper.log_jira_alert(error_message, group)
                        else:
                            logger.debug('pushing to jira from finding.finding_bulk_update_all()')
                            jira_helper.push_to_jira(group)
                            success_count += 1

                        jira_helper.push_to_jira(group)

                for error_message, error_count in error_counts.items():
                    add_error_message_to_response('%i finding groups could not be pushed to JIRA: %s' % (error_count, error_message))

                if success_count > 0:
                    add_success_message_to_response('%i finding groups pushed to JIRA succesfully' % success_count)

                # refresh from db
                finds = finds.all()

                error_counts = defaultdict(lambda: 0)
                success_count = 0
                for finding in finds:
                    from dojo.tools import tool_issue_updater
                    tool_issue_updater.async_tool_issue_update(finding)

                    # not sure yet if we want to support bulk unlink, so leave as commented out for now
                    # if form.cleaned_data['unlink_from_jira']:
                    #     if finding.has_jira_issue:
                    #         jira_helper.finding_unlink_jira(request, finding)

                    # Because we never call finding.save() in a bulk update, we need to actually
                    # push the JIRA stuff here, rather than in finding.save()

                    # can't use helper as when push_all_jira_issues is True, the checkbox gets disabled and is always false
                    # push_to_jira = jira_helper.is_push_to_jira(new_finding, form.cleaned_data.get('push_to_jira'))
                    if jira_helper.is_push_all_issues(finding) or form.cleaned_data.get('push_to_jira'):

                        can_be_pushed_to_jira, error_message, error_code = jira_helper.can_be_pushed_to_jira(finding)
                        if finding.has_jira_group_issue and not finding.has_jira_issue:
                            error_message = 'finding already pushed as part of Finding Group'
                            error_counts[error_message] += 1
                            jira_helper.log_jira_alert(error_message, finding)
                        elif not can_be_pushed_to_jira:
                            error_counts[error_message] += 1
                            jira_helper.log_jira_alert(error_message, finding)
                        else:
                            logger.debug('pushing to jira from finding.finding_bulk_update_all()')
                            jira_helper.push_to_jira(finding)
                            success_count += 1

                for error_message, error_count in error_counts.items():
                    add_error_message_to_response('%i findings could not be pushed to JIRA: %s' % (error_count, error_message))

                if success_count > 0:
                    add_success_message_to_response('%i findings pushed to JIRA succesfully' % success_count)

                if updated_find_count > 0:
                    messages.add_message(request,
                                        messages.SUCCESS,
                                        'Bulk update of {} findings was successful.'.format(updated_find_count),
                                        extra_tags='alert-success')
            else:
                messages.add_message(request,
                                     messages.ERROR,
                                     'Unable to process bulk update. Required fields were not selected.',
                                     extra_tags='alert-danger')

    if return_url:
        redirect(request, return_url)

    return redirect_to_return_url_or_else(request, None)


def find_available_notetypes(notes):
    single_note_types = Note_Type.objects.filter(is_single=True, is_active=True).values_list('id', flat=True)
    multiple_note_types = Note_Type.objects.filter(is_single=False, is_active=True).values_list('id', flat=True)
    available_note_types = []
    for note_type_id in multiple_note_types:
        available_note_types.append(note_type_id)
    for note_type_id in single_note_types:
        for note in notes:
            if note_type_id == note.note_type_id:
                break
        else:
            available_note_types.append(note_type_id)
    queryset = Note_Type.objects.filter(id__in=available_note_types).order_by('-id')
    return queryset


def get_missing_mandatory_notetypes(finding):
    notes = finding.notes.all()
    mandatory_note_types = Note_Type.objects.filter(is_mandatory=True, is_active=True).values_list('id', flat=True)
    notes_to_be_added = []
    for note_type_id in mandatory_note_types:
        for note in notes:
            if note_type_id == note.note_type_id:
                break
        else:
            notes_to_be_added.append(note_type_id)
    queryset = Note_Type.objects.filter(id__in=notes_to_be_added)
    return queryset


@user_is_authorized(Finding, Permissions.Finding_Edit, 'original_id', 'change')
@require_POST
def mark_finding_duplicate(request, original_id, duplicate_id):
    original = get_object_or_404(Finding, id=original_id)
    duplicate = get_object_or_404(Finding, id=duplicate_id)

    if original.test.engagement != duplicate.test.engagement:
        if original.test.engagement.deduplication_on_engagement or duplicate.test.engagement.deduplication_on_engagement:
            messages.add_message(
                request,
                messages.ERROR,
                'Marking finding as duplicate/original failed as they are not in the same engagement and deduplication_on_engagement is enabled for at least one of them',
                extra_tags='alert-danger')
            return redirect_to_return_url_or_else(request, reverse('view_finding', args=(duplicate.id,)))

    duplicate.duplicate = True
    duplicate.active = False
    duplicate.verified = False
    # make sure we don't create circular or transitive duplicates
    if original.duplicate:
        duplicate.duplicate_finding = original.duplicate_finding
    else:
        duplicate.duplicate_finding = original

    logger.debug('marking finding %i as duplicate of %i', duplicate.id, duplicate.duplicate_finding.id)

    duplicate.last_reviewed = timezone.now()
    duplicate.last_reviewed_by = request.user
    duplicate.save(dedupe_option=False)
    original.found_by.add(duplicate.test.test_type)
    original.save(dedupe_option=False)

    return redirect_to_return_url_or_else(request, reverse('view_finding', args=(duplicate.id,)))


def reset_finding_duplicate_status_internal(user, duplicate_id):
    duplicate = get_object_or_404(Finding, id=duplicate_id)

    if not duplicate.duplicate:
        return None

    logger.debug('resetting duplicate status of %i', duplicate.id)
    duplicate.duplicate = False
    duplicate.active = True
    if duplicate.duplicate_finding:
        # duplicate.duplicate_finding.original_finding.remove(duplicate)  # shouldn't be needed
        duplicate.duplicate_finding = None
    duplicate.last_reviewed = timezone.now()
    duplicate.last_reviewed_by = user
    duplicate.save(dedupe_option=False)

    return duplicate.id


@user_is_authorized(Finding, Permissions.Finding_Edit, 'duplicate_id', 'change')
@require_POST
def reset_finding_duplicate_status(request, duplicate_id):
    checked_duplicate_id = reset_finding_duplicate_status_internal(request.user, duplicate_id)
    if checked_duplicate_id is None:
        messages.add_message(
            request,
            messages.ERROR,
            "Can't reset duplicate status of a finding that is not a duplicate",
            extra_tags='alert-danger')
        return redirect_to_return_url_or_else(request, reverse('view_finding', args=(duplicate_id,)))

    return redirect_to_return_url_or_else(request, reverse('view_finding', args=(checked_duplicate_id,)))


def set_finding_as_original_internal(user, finding_id, new_original_id):
    finding = get_object_or_404(Finding, id=finding_id)
    new_original = get_object_or_404(Finding, id=new_original_id)

    if finding.test.engagement != new_original.test.engagement:
        if finding.test.engagement.deduplication_on_engagement or new_original.test.engagement.deduplication_on_engagement:
            return False

    if finding.duplicate or finding.original_finding.all():
        # existing cluster, so update all cluster members

        if finding.duplicate and finding.duplicate_finding:
            logger.debug('setting old original %i as duplicate of %i', finding.duplicate_finding.id, new_original.id)
            finding.duplicate_finding.duplicate_finding = new_original
            finding.duplicate_finding.duplicate = True
            finding.duplicate_finding.save(dedupe_option=False)

        for cluster_member in finding.duplicate_finding_set():
            if cluster_member != new_original:
                logger.debug('setting new original for %i to %i', cluster_member.id, new_original.id)
                cluster_member.duplicate_finding = new_original
                cluster_member.save(dedupe_option=False)

        logger.debug('setting new original for old root %i to %i', finding.id, new_original.id)
        finding.duplicate = True
        finding.duplicate_finding = new_original
        finding.save(dedupe_option=False)

    else:
        # creating a new cluster, so mark finding as duplicate
        logger.debug('marking %i as duplicate of %i', finding.id, new_original.id)
        finding.duplicate = True
        finding.active = False
        finding.duplicate_finding = new_original
        finding.last_reviewed = timezone.now()
        finding.last_reviewed_by = user
        finding.save(dedupe_option=False)

    logger.debug('marking new original %i as not duplicate', new_original.id)
    new_original.duplicate = False
    new_original.duplicate_finding = None
    new_original.save(dedupe_option=False)

    return True


@user_is_authorized(Finding, Permissions.Finding_Edit, 'finding_id', 'change')
@require_POST
def set_finding_as_original(request, finding_id, new_original_id):
    success = set_finding_as_original_internal(request.user, finding_id, new_original_id)
    if not success:
        messages.add_message(
            request,
            messages.ERROR,
            'Marking finding as duplicate/original failed as they are not in the same engagement and deduplication_on_engagement is enabled for at least one of them',
            extra_tags='alert-danger')

    return redirect_to_return_url_or_else(request, reverse('view_finding', args=(finding_id,)))


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'change')
@require_POST
def unlink_jira(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    logger.info('trying to unlink a linked jira issue from %d:%s', finding.id, finding.title)
    if finding.has_jira_issue:
        try:
            jira_helper.finding_unlink_jira(request, finding)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Link to JIRA issue succesfully deleted',
                extra_tags='alert-success')

            return JsonResponse({'result': 'OK'})
        except Exception as e:
            logger.exception(e)
            messages.add_message(
                request,
                messages.ERROR,
                'Link to JIRA could not be deleted, see alerts for details',
                extra_tags='alert-danger')

            return HttpResponse(status=500)
    else:
        messages.add_message(
            request,
            messages.ERROR,
            'Link to JIRA not found',
            extra_tags='alert-danger')
        return HttpResponse(status=400)


@user_is_authorized(Finding, Permissions.Finding_Edit, 'fid', 'change')
@require_POST
def push_to_jira(request, fid):
    finding = get_object_or_404(Finding, id=fid)
    try:
        logger.info('trying to push %d:%s to JIRA to create or update JIRA issue', finding.id, finding.title)
        logger.debug('pushing to jira from finding.push_to-jira()')

        # it may look like succes here, but the push_to_jira are swallowing exceptions
        # but cant't change too much now without having a test suite, so leave as is for now with the addition warning message to check alerts for background errors.
        if jira_helper.push_to_jira(finding):
            messages.add_message(
                request,
                messages.SUCCESS,
                message='Action queued to create or update linked JIRA issue, check alerts for background errors.',
                extra_tags='alert-success')
        else:
            messages.add_message(
                request,
                messages.SUCCESS,
                'Push to JIRA failed, check alerts on the top right for errors',
                extra_tags='alert-danger')

        return JsonResponse({'result': 'OK'})
    except Exception as e:
        logger.exception(e)
        logger.error('Error pushing to JIRA: ', exc_info=True)
        messages.add_message(
            request,
            messages.ERROR,
            'Error pushing to JIRA',
            extra_tags='alert-danger')
        return HttpResponse(status=500)
    # return redirect_to_return_url_or_else(request, reverse('view_finding', args=(finding.id,)))


# precalculate because we need related_actions to be set
def duplicate_cluster(request, finding):
    duplicate_cluster = finding.duplicate_finding_set()

    duplicate_cluster = prefetch_for_findings(duplicate_cluster)

    # populate actions for findings in duplicate cluster
    for duplicate_member in duplicate_cluster:
        duplicate_member.related_actions = calculate_possible_related_actions_for_similar_finding(request, finding, duplicate_member)

    return duplicate_cluster


# django doesn't allow much logic or even method calls with parameters in templates.
# so we have to use a function in this view to calculate the possible actions on a similar (or duplicate) finding.
# and we assign this dictionary to the finding so it can be accessed in the template.
# these actions are always calculated in the context of the finding the user is viewing
# because this determines which actions are possible
def calculate_possible_related_actions_for_similar_finding(request, finding, similar_finding):
    actions = []
    # logger.debug('all: %s', [s.id for s in similar_finding.original_finding.all()])
    if similar_finding.test.engagement != finding.test.engagement and (similar_finding.test.engagement.deduplication_on_engagement or finding.test.engagement.deduplication_on_engagement):
        actions.append({'action': 'None', 'reason': 'This finding is in a different engagement and deduplication_inside_engagment is enabled here or in that finding'})
    elif finding.duplicate_finding == similar_finding:
        actions.append({'action': 'None', 'reason': 'This finding is the root of the cluster, use an action on another row, or the finding on top of the page to change the root of the cluser'})
    elif similar_finding.original_finding.all():
        actions.append({'action': 'None', 'reason': 'This finding is similar, but is already an original in a different cluster. Remove it from that cluster before you connect it to this cluster.'})
    else:
        if similar_finding.duplicate_finding:
            # reset duplicate status is always possible
            actions.append({'action': 'reset_finding_duplicate_status', 'reason': 'This will remove the finding from the cluster, effectively marking it no longer as duplicate. Will not trigger deduplication logic after saving.'})

            # logger.debug(similar_finding.duplicate_finding)
            # logger.debug(finding)
            if similar_finding.duplicate_finding == finding or similar_finding.duplicate_finding == finding.duplicate_finding:
                # duplicate inside the same cluster
                actions.append({'action': 'set_finding_as_original', 'reason': 'Sets this finding as the Original for the whole cluster. The existing Original will be downgraded to become a member of the cluster and, together with the other members, will be marked as duplicate of the new Original.'})
            else:
                # duplicate inside different cluster
                actions.append({'action': 'mark_finding_duplicate', 'reason': 'Will mark this finding as duplicate of the root finding in this cluster, effectively adding it to the cluster and removing it from the other cluster.'})
        else:
            # similar is not a duplicate yet
            if finding.duplicate or finding.original_finding.all():
                actions.append({'action': 'mark_finding_duplicate', 'reason': 'Will mark this finding as duplicate of the root finding in this cluster'})
                actions.append({'action': 'set_finding_as_original', 'reason': 'Sets this finding as the Original for the whole cluster. The existing Original will be downgraded to become a member of the cluster and, together with the other members, will be marked as duplicate of the new Original.'})
            else:
                # similar_finding is not an original/root of a cluster as per earlier if clause
                actions.append({'action': 'mark_finding_duplicate', 'reason': 'Will mark this finding as duplicate of the finding on this page.'})
                actions.append({'action': 'set_finding_as_original', 'reason': 'Sets this finding as the Original marking the finding on this page as duplicate of this original.'})

    # logger.debug('related_actions for %i: %s', similar_finding.id, {finding.id: actions})

    return actions
