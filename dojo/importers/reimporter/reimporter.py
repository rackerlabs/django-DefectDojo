import datetime

from dojo.endpoint.utils import endpoint_get_or_create
from dojo.importers import utils as importer_utils
from dojo.models import Notes, Finding, \
    BurpRawRequestResponse, \
    Endpoint_Status, \
    Test_Import

from dojo.utils import get_current_user

from django.core.exceptions import MultipleObjectsReturned
from django.conf import settings
from django.utils import timezone
import dojo.notifications.helper as notifications_helper
import dojo.finding.helper as finding_helper
import dojo.jira_link.helper as jira_helper
import base64
import logging

logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


class DojoDefaultReImporter(object):

    def process_parsed_findings(self, test, parsed_findings, scan_type, user, active, verified, minimum_severity=None,
                                endpoints_to_add=None, push_to_jira=None, group_by=None, now=timezone.now()):

        items = parsed_findings
        original_items = list(test.finding_set.all())
        new_items = []
        mitigated_count = 0
        finding_count = 0
        finding_added_count = 0
        reactivated_count = 0
        reactivated_items = []
        unchanged_count = 0
        unchanged_items = []

        logger.debug('starting reimport of %i items.', len(items) if items else 0)
        from dojo.importers.reimporter.utils import get_deduplication_algorithm_from_conf, match_new_finding_to_existing_finding, update_endpoint_status
        deduplication_algorithm = get_deduplication_algorithm_from_conf(scan_type)

        i = 0
        logger.debug('STEP 1: looping over findings from the reimported report and trying to match them to existing findings')
        deduplicationLogger.debug('Algorithm used for matching new findings to existing findings: %s', deduplication_algorithm)
        for item in items:
            sev = item.severity
            if sev == 'Information' or sev == 'Informational':
                sev = 'Info'

            item.severity = sev
            item.numerical_severity = Finding.get_numerical_severity(sev)

            if (Finding.SEVERITIES[sev] >
                    Finding.SEVERITIES[minimum_severity]):
                # finding's severity is below the configured threshold : ignoring the finding
                continue

            # existing findings may be from before we had component_name/version fields
            component_name = item.component_name if hasattr(item, 'component_name') else None
            component_version = item.component_version if hasattr(item, 'component_version') else None

            if not hasattr(item, 'test'):
                item.test = test

            item.hash_code = item.compute_hash_code()
            deduplicationLogger.debug("item's hash_code: %s", item.hash_code)

            findings = match_new_finding_to_existing_finding(item, test, deduplication_algorithm, scan_type)

            deduplicationLogger.debug('found %i findings matching with current new finding', len(findings))

            if findings:
                # existing finding found
                finding = findings[0]
                if finding.false_p or finding.out_of_scope or finding.risk_accepted:
                    logger.debug('%i: skipping existing finding (it is marked as false positive:%s and/or out of scope:%s or is a risk accepted:%s): %i:%s:%s:%s', i, finding.false_p, finding.out_of_scope, finding.risk_accepted, finding.id, finding, finding.component_name, finding.component_version)
                elif finding.mitigated or finding.is_mitigated:
                    logger.debug('%i: reactivating: %i:%s:%s:%s', i, finding.id, finding, finding.component_name, finding.component_version)
                    finding.mitigated = None
                    finding.is_mitigated = False
                    finding.mitigated_by = None
                    finding.active = True
                    finding.verified = verified

                    # existing findings may be from before we had component_name/version fields
                    finding.component_name = finding.component_name if finding.component_name else component_name
                    finding.component_version = finding.component_version if finding.component_version else component_version

                    # don't dedupe before endpoints are added
                    finding.save(dedupe_option=False)
                    note = Notes(
                        entry="Re-activated by %s re-upload." % scan_type,
                        author=user)
                    note.save()
                    endpoint_status = finding.endpoint_status.all()
                    for status in endpoint_status:
                        status.mitigated_by = None
                        status.mitigated_time = None
                        status.mitigated = False
                        status.last_modified = timezone.now()
                        status.save()
                    finding.notes.add(note)
                    reactivated_items.append(finding)
                    reactivated_count += 1
                else:
                    # existing findings may be from before we had component_name/version fields
                    logger.debug('%i: updating existing finding: %i:%s:%s:%s', i, finding.id, finding, finding.component_name, finding.component_version)
                    if not finding.component_name or not finding.component_version:
                        finding.component_name = finding.component_name if finding.component_name else component_name
                        finding.component_version = finding.component_version if finding.component_version else component_version
                        finding.save(dedupe_option=False)

                    unchanged_items.append(finding)
                    unchanged_count += 1
                if finding.dynamic_finding:
                    logger.debug("Re-import found an existing dynamic finding for this new finding. Checking the status of endpoints")
                    update_endpoint_status(finding, item, user)
            else:
                # no existing finding found
                item.reporter = user
                item.last_reviewed = timezone.now()
                item.last_reviewed_by = user
                item.verified = verified
                item.active = active
                # Save it. Don't dedupe before endpoints are added.
                item.save(dedupe_option=False)
                logger.debug('%i: reimport created new finding as no existing finding match: %i:%s:%s:%s', i, item.id, item, item.component_name, item.component_version)

                # only new items get auto grouped to avoid confusion around already existing items that are already grouped
                if settings.FEATURE_FINDING_GROUPS and group_by:
                    finding_helper.add_finding_to_auto_group(item, group_by)

                finding_added_count += 1
                new_items.append(item)
                finding = item

                if hasattr(item, 'unsaved_req_resp'):
                    for req_resp in item.unsaved_req_resp:
                        burp_rr = BurpRawRequestResponse(
                            finding=finding,
                            burpRequestBase64=base64.b64encode(req_resp["req"].encode("utf-8")),
                            burpResponseBase64=base64.b64encode(req_resp["resp"].encode("utf-8")))
                        burp_rr.clean()
                        burp_rr.save()

                if item.unsaved_request and item.unsaved_response:
                    burp_rr = BurpRawRequestResponse(
                        finding=finding,
                        burpRequestBase64=base64.b64encode(item.unsaved_request.encode()),
                        burpResponseBase64=base64.b64encode(item.unsaved_response.encode()))
                    burp_rr.clean()
                    burp_rr.save()

            # for existing findings: make sure endpoints are present or created
            if finding:
                finding_count += 1
                for endpoint in item.unsaved_endpoints:
                    try:
                        endpoint.clean()
                    except ValidationError as e:
                        logger.warning("DefectDojo is storing broken endpoint because cleaning wasn't successful: "
                                       "{}".format(e))

                    try:
                        ep, created = endpoint_get_or_create(
                            protocol=endpoint.protocol,
                            userinfo=endpoint.userinfo,
                            host=endpoint.host,
                            port=endpoint.port,
                            path=endpoint.path,
                            query=endpoint.query,
                            fragment=endpoint.fragment,
                            product=test.engagement.product)
                    except (MultipleObjectsReturned):
                        pass

                    try:
                        eps, created = Endpoint_Status.objects.get_or_create(
                            finding=finding,
                            endpoint=ep)
                    except (MultipleObjectsReturned):
                        pass

                    ep.endpoint_status.add(eps)
                    finding.endpoints.add(ep)
                    finding.endpoint_status.add(eps)

                if endpoints_to_add:
                    for endpoint in endpoints_to_add:
                        # TODO Not sure what happens here, we get an endpoint model and try to create it again?
                        try:
                            endpoint.clean()
                        except ValidationError as e:
                            logger.warning("DefectDojo is storing broken endpoint because cleaning wasn't successful: "
                                           "{}".format(e))

                        try:
                            ep, created = endpoint_get_or_create(
                                protocol=endpoint.protocol,
                                userinfo=endpoint.userinfo,
                                host=endpoint.host,
                                port=endpoint.port,
                                path=endpoint.path,
                                query=endpoint.query,
                                fragment=endpoint.fragment,
                                product=test.engagement.product)
                        except (MultipleObjectsReturned):
                            pass
                        try:
                            eps, created = Endpoint_Status.objects.get_or_create(
                                finding=finding,
                                endpoint=ep)
                        except (MultipleObjectsReturned):
                            pass

                        ep.endpoint_status.add(eps)
                        finding.endpoints.add(ep)
                        finding.endpoint_status.add(eps)

                if item.unsaved_tags:
                    finding.tags = item.unsaved_tags

                # existing findings may be from before we had component_name/version fields
                finding.component_name = finding.component_name if finding.component_name else component_name
                finding.component_version = finding.component_version if finding.component_version else component_version

                # finding = new finding or existing finding still in the upload report
                # to avoid pushing a finding group multiple times, we push those outside of the loop
                if settings.FEATURE_FINDING_GROUPS and finding.finding_group:
                    finding.save()
                else:
                    finding.save(push_to_jira=push_to_jira)

        to_mitigate = set(original_items) - set(reactivated_items) - set(unchanged_items)
        untouched = set(unchanged_items) - set(to_mitigate)

        if settings.FEATURE_FINDING_GROUPS and push_to_jira:
            for finding_group in set([finding.finding_group for finding in reactivated_items + unchanged_items + new_items if finding.finding_group is not None]):
                jira_helper.push_to_jira(finding_group)

        return new_items, reactivated_items, to_mitigate, untouched

    def close_old_findings(self, test, to_mitigate, scan_date_time, user, push_to_jira=None):
        logger.debug('IMPORT_SCAN: Closing findings no longer present in scan report')
        mitigated_findings = []
        for finding in to_mitigate:
            if not finding.mitigated or not finding.is_mitigated:
                logger.debug('mitigating finding: %i:%s', finding.id, finding)
                finding.mitigated = scan_date_time
                finding.is_mitigated = True
                finding.mitigated_by = user
                finding.active = False

                endpoint_status = finding.endpoint_status.all()
                for status in endpoint_status:
                    status.mitigated_by = user
                    status.mitigated_time = timezone.now()
                    status.mitigated = True
                    status.last_modified = timezone.now()
                    status.save()

                # to avoid pushing a finding group multiple times, we push those outside of the loop
                if settings.FEATURE_FINDING_GROUPS and finding.finding_group:
                    # don't try to dedupe findings that we are closing
                    finding.save(dedupe_option=False)
                else:
                    finding.save(push_to_jira=push_to_jira, dedupe_option=False)

                note = Notes(entry="Mitigated by %s re-upload." % test.test_type,
                            author=user)
                note.save()
                finding.notes.add(note)
                mitigated_findings.append(finding)

        if settings.FEATURE_FINDING_GROUPS and push_to_jira:
            for finding_group in set([finding.finding_group for finding in to_mitigate if finding.finding_group is not None]):
                jira_helper.push_to_jira(finding_group)

        return mitigated_findings

    def reimport_scan(self, scan, scan_type, test, active=True, verified=True, tags=None, minimum_severity=None,
                    user=None, endpoints_to_add=None, scan_date=None, version=None, branch_tag=None, build_id=None,
                    commit_hash=None, push_to_jira=None, close_old_findings=True, group_by=None, sonarqube_config=None):

        logger.debug(f'REIMPORT_SCAN: parameters: {locals()}')

        user = user or get_current_user()

        now = timezone.now()
        # retain weird existing logic to use current time for provided scan date
        scan_date_time = datetime.datetime.combine(scan_date, timezone.now().time())
        if settings.USE_TZ:
            scan_date_time = timezone.make_aware(scan_date_time, timezone.get_default_timezone())

        if sonarqube_config:  # it there is not sonarqube_config, just use original
            if sonarqube_config.product != test.engagement.product:
                raise ValidationError('"sonarqube_config" has to be from same product as "test"')

            if test.sonarqube_config != sonarqube_config:  # update of sonarqube_config
                test.sonarqube_config = sonarqube_config
                test.save()

        logger.debug('REIMPORT_SCAN: Parse findings')
        parsed_findings = importer_utils.parse_findings(scan, test, active, verified, scan_type)

        logger.debug('REIMPORT_SCAN: Processing findings')
        new_findings, reactivated_findings, findings_to_mitigate, untouched_findings = \
            self.process_parsed_findings(test, parsed_findings, scan_type, user, active, verified,
                                         minimum_severity=minimum_severity, endpoints_to_add=endpoints_to_add,
                                         push_to_jira=push_to_jira, group_by=group_by, now=now)

        closed_findings = []
        if close_old_findings:
            logger.debug('REIMPORT_SCAN: Closing findings no longer present in scan report')
            closed_findings = self.close_old_findings(test, findings_to_mitigate, scan_date_time, user=user, push_to_jira=push_to_jira)

        logger.debug('REIMPORT_SCAN: Updating test/engagement timestamps')
        importer_utils.update_timestamps(test, scan_date, version, branch_tag, build_id, commit_hash, now, scan_date_time)

        if settings.TRACK_IMPORT_HISTORY:
            logger.debug('REIMPORT_SCAN: Updating Import History')
            importer_utils.update_import_history(Test_Import.REIMPORT_TYPE, active, verified, tags, minimum_severity, endpoints_to_add,
                                                 version, branch_tag, build_id, commit_hash, push_to_jira, close_old_findings,
                                                 test, new_findings, closed_findings, reactivated_findings)

        logger.debug('REIMPORT_SCAN: Generating notifications')

        updated_count = len(closed_findings) + len(reactivated_findings) + len(new_findings)
        if updated_count > 0:
            notifications_helper.notify_scan_added(test, updated_count, new_findings=new_findings, findings_mitigated=closed_findings,
                                                    findings_reactivated=reactivated_findings, findings_untouched=untouched_findings)

        logger.debug('REIMPORT_SCAN: Done')

        return test, updated_count, len(new_findings), len(closed_findings), len(reactivated_findings), len(untouched_findings)
