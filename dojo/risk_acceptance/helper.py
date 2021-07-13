from django.core.exceptions import PermissionDenied
from django.utils import timezone
from dojo.utils import get_system_setting, get_full_url
from dateutil.relativedelta import relativedelta
import dojo.jira_link.helper as jira_helper
from dojo.jira_link.helper import escape_for_jira
from dojo.notifications.helper import create_notification
from django.urls import reverse
from dojo.celery import app
from dojo.models import System_Settings, Risk_Acceptance
import logging

logger = logging.getLogger(__name__)


def expire_now(risk_acceptance):
    logger.info('Expiring risk acceptance %i:%s with %i findings', risk_acceptance.id, risk_acceptance, len(risk_acceptance.accepted_findings.all()))

    reactivated_findings = []
    if risk_acceptance.reactivate_expired:
        for finding in risk_acceptance.accepted_findings.all():
            if not finding.active:
                logger.debug('%i:%s: unaccepting a.k.a reactivating finding.', finding.id, finding)
                finding.active = True
                finding.risk_accepted = False

                if risk_acceptance.restart_sla_expired:
                    finding.sla_start_date = timezone.now().date()

                finding.save(dedupe_option=False)
                reactivated_findings.append(finding)
                # findings remain in this risk acceptance for reporting / metrics purposes
            else:
                logger.debug('%i:%s already active, no changes made.', finding.id, finding)

        # best effort JIRA integration, no status changes
        post_jira_comments(risk_acceptance, risk_acceptance.accepted_findings.all(), expiration_message_creator)

    risk_acceptance.expiration_date = timezone.now()
    risk_acceptance.expiration_date_handled = timezone.now()
    risk_acceptance.save()

    accepted_findings = risk_acceptance.accepted_findings.all()
    title = 'Risk acceptance with ' + str(len(accepted_findings)) + " accepted findings has expired for " + \
            str(risk_acceptance.engagement.product) + ': ' + str(risk_acceptance.engagement.name)

    create_notification(event='risk_acceptance_expiration', title=title, risk_acceptance=risk_acceptance, accepted_findings=accepted_findings,
                         reactivated_findings=reactivated_findings, engagement=risk_acceptance.engagement,
                         product=risk_acceptance.engagement.product,
                         url=reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id, )))


def reinstate(risk_acceptance, old_expiration_date):
    if risk_acceptance.expiration_date_handled:
        logger.info('Reinstating risk acceptance %i:%s with %i findings', risk_acceptance.id, risk_acceptance, len(risk_acceptance.accepted_findings.all()))

        expiration_delta_days = get_system_setting('risk_acceptance_form_default_days', 90)
        risk_acceptance.expiration_date = timezone.now() + relativedelta(days=expiration_delta_days)

        reinstated_findings = []
        for finding in risk_acceptance.accepted_findings.all():
            if finding.active:
                logger.debug('%i:%s: accepting a.k.a. deactivating finding', finding.id, finding)
                finding.active = False
                finding.risk_accepted = True
                finding.save(dedupe_option=False)
                reinstated_findings.append(finding)
            else:
                logger.debug('%i:%s: already inactive, not making any changes', finding.id, finding)

        # best effort JIRA integration, no status changes
        post_jira_comments(risk_acceptance, risk_acceptance.accepted_findings.all(), reinstation_message_creator)

    risk_acceptance.expiration_date_handled = None
    risk_acceptance.expiration_date_warned = None
    risk_acceptance.save()


def delete(eng, risk_acceptance):
    findings = risk_acceptance.accepted_findings.all()
    for finding in findings:
        finding.active = True
        finding.risk_accepted = False
        finding.save(dedupe_option=False)

    # best effort jira integration, no status changes
    post_jira_comments(risk_acceptance, findings, unaccepted_message_creator)

    risk_acceptance.accepted_findings.clear()
    eng.risk_acceptance.remove(risk_acceptance)
    eng.save()

    for note in risk_acceptance.notes.all():
        note.delete()

    risk_acceptance.path.delete()
    risk_acceptance.delete()


def remove_finding_from_risk_acceptance(risk_acceptance, finding):
    logger.debug('removing finding %i from risk acceptance %i', finding.id, risk_acceptance.id)
    risk_acceptance.accepted_findings.remove(finding)
    finding.active = True
    finding.risk_accepted = False
    finding.save(dedupe_option=False)
    # best effort jira integration, no status changes
    post_jira_comments(risk_acceptance, [finding], unaccepted_message_creator)


def add_findings_to_risk_acceptance(risk_acceptance, findings):
    for finding in findings:
        if not finding.duplicate:
            finding.active = False
            finding.risk_accepted = True
            finding.save(dedupe_option=False)
            risk_acceptance.accepted_findings.add(finding)
    risk_acceptance.save()

    # best effort jira integration, no status changes
    post_jira_comments(risk_acceptance, findings, accepted_message_creator)


@app.task
def expiration_handler(*args, **kwargs):
    """
    Creates a notification upon risk expiration and X days beforehand if configured.
    This notification is 1 per risk acceptance.

    If configured also sends a JIRA comment in both case to each jira issue.
    This is per finding.
    """

    try:
        system_settings = System_Settings.objects.get()
    except System_Settings.DoesNotExist:
        logger.warn("Unable to get system_settings, skipping risk acceptance expiration job")

    risk_acceptances = get_expired_risk_acceptances_to_handle()

    logger.info('expiring %i risk acceptances that are past expiration date', len(risk_acceptances))
    for risk_acceptance in risk_acceptances:
        expire_now(risk_acceptance)
        # notification created by expire_now code

    heads_up_days = system_settings.risk_acceptance_notify_before_expiration
    if heads_up_days > 0:
        risk_acceptances = get_almost_expired_risk_acceptances_to_handle(heads_up_days)

        logger.info('notifying for %i risk acceptances that are expiring within %i days', len(risk_acceptances), heads_up_days)
        for risk_acceptance in risk_acceptances:
            logger.debug('notifying for risk acceptance %i:%s with %i findings', risk_acceptance.id, risk_acceptance, len(risk_acceptance.accepted_findings.all()))

            notification_title = 'Risk acceptance with ' + str(len(risk_acceptance.accepted_findings.all())) + " accepted findings will expire on " + \
                timezone.localtime(risk_acceptance.expiration_date).strftime("%b %d, %Y") + " for " + \
                str(risk_acceptance.engagement.product) + ': ' + str(risk_acceptance.engagement.name)

            create_notification(event='risk_acceptance_expiration', title=notification_title, risk_acceptance=risk_acceptance,
                                accepted_findings=risk_acceptance.accepted_findings.all(), engagement=risk_acceptance.engagement,
                                product=risk_acceptance.engagement.product,
                                url=reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id, )))

            post_jira_comments(risk_acceptance, expiration_warning_message_creator, heads_up_days)

            risk_acceptance.expiration_date_warned = timezone.now()
            risk_acceptance.save()


def expiration_message_creator(risk_acceptance, heads_up_days=0):
    return 'Risk acceptance [(%s)|%s] with %i findings has expired' % \
        (escape_for_jira(risk_acceptance.name),
        get_full_url(reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id))),
        len(risk_acceptance.accepted_findings.all()))


def expiration_warning_message_creator(risk_acceptance, heads_up_days=0):
    return 'Risk acceptance [(%s)|%s] with %i findings will expire in %i days' % \
        (escape_for_jira(risk_acceptance.name),
        get_full_url(reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id))),
        len(risk_acceptance.accepted_findings.all()), heads_up_days)


def reinstation_message_creator(risk_acceptance, heads_up_days=0):
    return 'Risk acceptance [(%s)|%s] with %i findings has been reinstated (expires on %s)' % \
        (escape_for_jira(risk_acceptance.name),
        get_full_url(reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id))),
        len(risk_acceptance.accepted_findings.all()), timezone.localtime(risk_acceptance.expiration_date).strftime("%b %d, %Y"))


def accepted_message_creator(risk_acceptance, heads_up_days=0):
    if risk_acceptance:
        return 'Finding has been added to risk acceptance [(%s)|%s] with %i findings (expires on %s)' % \
            (escape_for_jira(risk_acceptance.name),
            get_full_url(reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id))),
            len(risk_acceptance.accepted_findings.all()), timezone.localtime(risk_acceptance.expiration_date).strftime("%b %d, %Y"))
    else:
        return 'Finding has been risk accepted'


def unaccepted_message_creator(risk_acceptance, heads_up_days=0):
    if risk_acceptance:
        return 'finding was unaccepted/deleted from risk acceptance [(%s)|%s]' % \
            (escape_for_jira(risk_acceptance.name),
            get_full_url(reverse('view_risk_acceptance', args=(risk_acceptance.engagement.id, risk_acceptance.id))))
    else:
        return 'Finding is no longer risk accepted'


def post_jira_comment(finding, message_factory, heads_up_days=0):
    if not finding or not finding.has_jira_issue:
        return

    jira_project = jira_helper.get_jira_project(finding)

    if jira_project and jira_project.risk_acceptance_expiration_notification:
        jira_instance = jira_helper.get_jira_instance(finding)

        if jira_instance:

            jira_comment = message_factory(None, heads_up_days)

            logger.debug("Creating JIRA comment for something risk acceptance related")
            jira_helper.add_simple_jira_comment(jira_instance, finding.jira_issue, jira_comment)


def post_jira_comments(risk_acceptance, findings, message_factory, heads_up_days=0):
    if not risk_acceptance:
        return

    jira_project = jira_helper.get_jira_project(risk_acceptance.engagement)

    if jira_project and jira_project.risk_acceptance_expiration_notification:
        jira_instance = jira_helper.get_jira_instance(risk_acceptance.engagement)

        if jira_instance:
            jira_comment = message_factory(risk_acceptance, heads_up_days)

            for finding in findings:
                if finding.has_jira_issue:
                    logger.debug("Creating JIRA comment for something risk acceptance related")
                    jira_helper.add_simple_jira_comment(jira_instance, finding.jira_issue, jira_comment)


def get_expired_risk_acceptances_to_handle():
    risk_acceptances = Risk_Acceptance.objects.filter(expiration_date__isnull=False, expiration_date_handled__isnull=True, expiration_date__date__lte=timezone.now().date())
    return prefetch_for_expiration(risk_acceptances)


def get_almost_expired_risk_acceptances_to_handle(heads_up_days):
    risk_acceptances = Risk_Acceptance.objects.filter(expiration_date__isnull=False, expiration_date_handled__isnull=True, expiration_date_warned__isnull=True,
            expiration_date__date__lte=timezone.now().date() + relativedelta(days=heads_up_days), expiration_date__date__gte=timezone.now().date())
    return prefetch_for_expiration(risk_acceptances)


def prefetch_for_expiration(risk_acceptances):
    return risk_acceptances.prefetch_related('accepted_findings', 'accepted_findings__jira_issue',
                                                'engagement_set',
                                                'engagement__jira_project',
                                                'engagement__jira_project__jira_instance'
                                             )


def simple_risk_accept(finding, perform_save=True):
    if not finding.test.engagement.product.enable_simple_risk_acceptance:
        raise PermissionDenied()

    logger.debug('accepting finding %i:%s', finding.id, finding)
    finding.risk_accepted = True
    # risk accepted, so finding no longer considered active
    finding.active = False
    if perform_save:
        finding.save(dedupe_option=False)
    # post_jira_comment might reload from database so see unaccepted finding. but the comment
    # only contains some text so that's ok
    post_jira_comment(finding, accepted_message_creator)


def risk_unaccept(finding, perform_save=True):
    logger.debug('unaccepting finding %i:%s if it is currently risk accepted', finding.id, finding)
    if finding.risk_accepted:
        logger.debug('unaccepting finding %i:%s', finding.id, finding)
        # keep reference to ra to for posting comments later
        risk_acceptance = finding.risk_acceptance
        # removing from ManyToMany will not fail for non-existing entries
        remove_from_any_risk_acceptance(finding)
        if not finding.mitigated and not finding.false_p and not finding.out_of_scope:
            finding.active = True
        finding.risk_accepted = False
        if perform_save:
            logger.debug('saving unaccepted finding %i:%s', finding.id, finding)
            finding.save(dedupe_option=False)

        # post_jira_comment might reload from database so see unaccepted finding. but the comment
        # only contains some text so that's ok
        post_jira_comment(finding, unaccepted_message_creator)


def remove_from_any_risk_acceptance(finding):
    for r in finding.risk_acceptance_set.all():
        r.accepted_findings.remove(finding)
