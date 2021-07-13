from dateutil.relativedelta import relativedelta
from dojo.utils import get_system_setting
from django.utils import timezone
from django.utils.http import urlencode
from django.urls import reverse
from .dojo_test_case import DojoTestCase
from dojo.models import Risk_Acceptance, Finding, System_Settings
# from unittest.mock import patch
from django.utils.datastructures import MultiValueDict
from django.db.models import Q
import copy
# from unittest import skip
import dojo.risk_acceptance.helper as ra_helper
import logging

logger = logging.getLogger(__name__)


class RiskAcceptanceTestUI(DojoTestCase):
    fixtures = ['dojo_testdata.json']

    data_risk_accceptance = {
        'name': 'Accept: Unit test',
        'accepted_findings': [72808],
        'recommendation': 'A',
        'recommendation_details': 'recommendation 1',
        'decision': 'A',
        'decision_details': 'it has been decided!',
        'accepted_by': 'pointy haired boss',
        # 'path: (binary)
        'owner': 1,
        'expiration_date': '2021-07-15',
        'reactivate_expired': True
    }

    data_remove_finding_from_ra = {
        'remove_finding': 'Remove',
        'remove_finding_id': 666,
    }

    def __init__(self, *args, **kwargs):
        DojoTestCase.__init__(self, *args, **kwargs)

    def setUp(self):
        self.system_settings(enable_jira=True)
        self.client.force_login(self.get_test_admin())

    def add_risk_acceptance(self, eid, data_risk_accceptance, fid=None):

        if fid:
            args = (eid, fid, )
        else:
            args = (eid, )

        response = self.client.post(reverse('add_risk_acceptance', args=args), data_risk_accceptance)
        self.assertEqual(302, response.status_code, response.content[:1000])
        return response

    def assert_all_active_not_risk_accepted(self, findings):
        if not all(finding.active for finding in findings):
            return False

        if not any(finding.risk_accepted for finding in findings):
            return True

        return False

    def assert_all_inactive_risk_accepted(self, findings):
        if any(finding.active for finding in findings):
            return False

        if all(finding.risk_accepted for finding in findings):
            return True

        return False

    def test_add_risk_acceptance_single_findings_accepted(self):
        ra_data = copy.copy(self.data_risk_accceptance)
        ra_data['accepted_findings'] = [2]
        ra_data['return_url'] = reverse('view_finding', args=(2, ))
        response = self.add_risk_acceptance(1, ra_data, 2)
        self.assertEqual('/finding/2', response.url)
        ra = Risk_Acceptance.objects.last()
        self.assert_all_active_not_risk_accepted(ra.accepted_findings.all())

    def test_add_risk_acceptance_multiple_findings_accepted(self):
        ra_data = copy.copy(self.data_risk_accceptance)
        ra_data['accepted_findings'] = [2, 3]
        response = self.add_risk_acceptance(1, ra_data)
        self.assertEqual('/engagement/1', response.url)
        ra = Risk_Acceptance.objects.last()
        self.assert_all_active_not_risk_accepted(ra.accepted_findings.all())

    def test_add_findings_to_risk_acceptance_findings_accepted(self):
        # create risk acceptance first
        self.test_add_risk_acceptance_multiple_findings_accepted()
        ra = Risk_Acceptance.objects.last()

        data_add_findings_to_ra = {
            'add_findings': 'Add Selected Findings',
            'accepted_findings': [4, 5]
        }

        response = self.client.post(reverse('view_risk_acceptance', args=(1, ra.id)),
                    urlencode(MultiValueDict(data_add_findings_to_ra), doseq=True),
                    content_type='application/x-www-form-urlencoded')

        self.assertEqual(302, response.status_code, response.content[:1000])
        self.assert_all_inactive_risk_accepted(Finding.objects.filter(id__in=[2, 3, 4, 5]))

    def test_remove_findings_from_risk_acceptance_findings_active(self):
        # create risk acceptance first
        self.test_add_risk_acceptance_multiple_findings_accepted()

        data = copy.copy(self.data_remove_finding_from_ra)
        data['remove_finding_id'] = 2
        ra = Risk_Acceptance.objects.last()
        response = self.client.post(reverse('view_risk_acceptance', args=(1, ra.id)), data)
        self.assertEqual(302, response.status_code, response.content[:1000])
        self.assert_all_active_not_risk_accepted(Finding.objects.filter(id=2))
        self.assert_all_inactive_risk_accepted(Finding.objects.filter(id=3))

    def test_remove_risk_acceptance_findings_active(self):
        self.test_add_risk_acceptance_multiple_findings_accepted()
        ra = Risk_Acceptance.objects.last()

        findings = ra.accepted_findings.all()

        data = {'id': ra.id}

        response = self.client.post(reverse('delete_risk_acceptance', args=(1, ra.id, )), data)

        self.assert_all_active_not_risk_accepted(findings)
        self.assert_all_active_not_risk_accepted(Finding.objects.filter(test__engagement=1))

    def test_expire_risk_acceptance_findings_active(self):
        self.test_add_risk_acceptance_multiple_findings_accepted()
        ra = Risk_Acceptance.objects.last()
        # ra.reactivate_expired = True # default True
        # ra.save()

        findings = ra.accepted_findings.all()

        data = {'id': ra.id}

        response = self.client.post(reverse('expire_risk_acceptance', args=(1, ra.id, )), data)

        ra.refresh_from_db()
        self.assert_all_active_not_risk_accepted(findings)
        self.assertEqual(ra.expiration_date.date(), timezone.now().date())
        self.assertEqual(ra.expiration_date_handled.date(), timezone.now().date())
        self.assertIsNone(ra.expiration_date_warned)

        self.assert_all_active_not_risk_accepted(Finding.objects.filter(test__engagement=1))
        # findings remain in (expired) risk acceptance
        self.assertTrue(all(finding in ra.accepted_findings.all() for finding in findings))

    def test_expire_risk_acceptance_findings_not_active(self):
        self.test_add_risk_acceptance_multiple_findings_accepted()
        ra = Risk_Acceptance.objects.last()
        ra.reactivate_expired = False
        ra.save()

        findings = ra.accepted_findings.all()

        data = {'id': ra.id}

        response = self.client.post(reverse('expire_risk_acceptance', args=(1, ra.id, )), data)

        ra.refresh_from_db()
        # no reactivation on expiry
        self.assert_all_inactive_risk_accepted(findings)
        self.assertEqual(ra.expiration_date.date(), timezone.now().date())
        self.assertEqual(ra.expiration_date_handled.date(), timezone.now().date())
        self.assertIsNone(ra.expiration_date_warned)

        self.assert_all_active_not_risk_accepted(Finding.objects.filter(test__engagement=1).filter(~Q(id=2)))
        # findings remain in (expired) risk acceptance
        self.assertTrue(all(finding in ra.accepted_findings.all() for finding in findings))

    def test_expire_risk_acceptance_sla_not_reset(self):
        self.test_add_risk_acceptance_multiple_findings_accepted()
        ra = Risk_Acceptance.objects.last()
        # ra.restart_sla_expired = False # default is False
        # ra.save()

        findings = ra.accepted_findings.all()

        data = {'id': ra.id}

        response = self.client.post(reverse('expire_risk_acceptance', args=(1, ra.id, )), data)

        ra.refresh_from_db()

        self.assertTrue(all(finding.sla_start_date != timezone.now().date() for finding in findings))

    def test_expire_risk_acceptance_sla_reset(self):
        self.test_add_risk_acceptance_multiple_findings_accepted()
        ra = Risk_Acceptance.objects.last()
        ra.restart_sla_expired = True
        ra.save()

        findings = ra.accepted_findings.all()

        data = {'id': ra.id}

        response = self.client.post(reverse('expire_risk_acceptance', args=(1, ra.id, )), data)

        ra.refresh_from_db()

        self.assertTrue(all(finding.sla_start_date == timezone.now().date() for finding in findings))

    def test_reinstate_risk_acceptance_findings_accepted(self):
        # first create an expired risk acceptance
        self.test_expire_risk_acceptance_findings_active()
        ra = Risk_Acceptance.objects.last()

        findings = ra.accepted_findings.all()

        data = {'id': ra.id}

        response = self.client.post(reverse('reinstate_risk_acceptance', args=(1, ra.id, )), data)

        ra.refresh_from_db()
        expiration_delta_days = get_system_setting('risk_acceptance_form_default_days', 90)
        risk_acceptance_expiration_date = timezone.now() + relativedelta(days=expiration_delta_days)

        self.assertEqual(ra.expiration_date.date(), risk_acceptance_expiration_date.date())
        self.assertIsNone(ra.expiration_date_handled)
        self.assertIsNone(ra.expiration_date_warned)
        self.assert_all_inactive_risk_accepted(findings)
        self.assert_all_active_not_risk_accepted(Finding.objects.filter(test__engagement=1).filter(~Q(id=2)))
        # findings remain in (expired) risk acceptance
        self.assertTrue(all(finding in ra.accepted_findings.all() for finding in findings))

    def create_multiple_ras(self):
        ra_data = copy.copy(self.data_risk_accceptance)
        ra_data['accepted_findings'] = [2]
        ra_data['return_url'] = reverse('view_finding', args=(2, ))
        response = self.add_risk_acceptance(1, ra_data, 2)
        ra1 = Risk_Acceptance.objects.last()

        ra_data = copy.copy(self.data_risk_accceptance)
        ra_data['accepted_findings'] = [7]
        ra_data['return_url'] = reverse('view_finding', args=(7, ))
        response = self.add_risk_acceptance(1, ra_data, 7)
        ra2 = Risk_Acceptance.objects.last()

        ra_data = copy.copy(self.data_risk_accceptance)
        ra_data['accepted_findings'] = [22]
        ra_data['return_url'] = reverse('view_finding', args=(22, ))
        response = self.add_risk_acceptance(3, ra_data, 22)
        ra3 = Risk_Acceptance.objects.last()

        return ra1, ra2, ra3

    def test_expiration_handler(self):
        ra1, ra2, ra3 = self.create_multiple_ras()
        system_settings = System_Settings.objects.get()
        system_settings.risk_acceptance_notify_before_expiration = 10
        system_settings.save()
        heads_up_days = system_settings.risk_acceptance_notify_before_expiration

        # ra1: expire in 9 days -> warn:yes, expire:no
        # ra2: expire in 11 days -> warn:no, expire:no
        # ra3: expire 5 days ago -> warn:no, expire:yes (expiration not handled yet, so expire)
        ra1.expiration_date = timezone.now().date() + relativedelta(days=heads_up_days - 1)
        ra2.expiration_date = timezone.now().date() + relativedelta(days=heads_up_days + 1)
        ra3.expiration_date = timezone.now().date() - relativedelta(days=5)
        ra1.save()
        ra2.save()
        ra3.save()

        to_warn = ra_helper.get_almost_expired_risk_acceptances_to_handle(heads_up_days=heads_up_days)
        to_expire = ra_helper.get_expired_risk_acceptances_to_handle()

        self.assertTrue(ra1 in to_warn)
        self.assertFalse(ra2 in to_warn)
        self.assertFalse(ra3 in to_warn)

        self.assertFalse(ra1 in to_expire)
        self.assertFalse(ra2 in to_expire)
        self.assertTrue(ra3 in to_expire)

        # run job
        ra_helper.expiration_handler()

        ra1.refresh_from_db()
        ra2.refresh_from_db()
        ra3.refresh_from_db()

        self.assertIsNotNone(ra1.expiration_date_warned)
        self.assertIsNone(ra2.expiration_date_warned)
        self.assertIsNone(ra3.expiration_date_warned)

        self.assertIsNone(ra1.expiration_date_handled)
        self.assertIsNone(ra2.expiration_date_handled)
        self.assertIsNotNone(ra3.expiration_date_handled)

        to_warn = ra_helper.get_almost_expired_risk_acceptances_to_handle(heads_up_days=heads_up_days)
        to_expire = ra_helper.get_expired_risk_acceptances_to_handle()

        # after handling no ra should be select for anything
        self.assertFalse(any(ra in to_warn for ra in [ra1, ra2, ra3]))
        self.assertFalse(any(ra in to_expire for ra in [ra1, ra2, ra3]))
