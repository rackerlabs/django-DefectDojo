from django.urls import reverse
from dojo.models import User, Test
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from django.test.client import Client
from .dojo_test_case import DojoAPITestCase

# from unittest import skip
import logging


logger = logging.getLogger(__name__)


# 0_zap_sample.xml: basic file with 4 out of 5 findings reported, zap4 absent
# 1 active
# 2 active
# 3 active
# 4 absent
# 5 active

# 1_zap_sample_0_and_new_absent: based on 0, but zap1 absent, zap4 reported
# 1 absent
# 2 active
# 3 active
# 4 active
# 5 active

# 2_zap_sample_0_and_new_endpoint: bases on 0: just adding an endpoint to zap1
# 1 active, extra endpoint
# 2 active
# 3 active
# 4 absent
# 5 active

# 3_zap_sampl_0_and_different_severities
# 1 active
# 2 active sev medium
# 3 active
# 4 absent
# 5 active sev medium

# test methods to be used both by API Test and UI Test
class ImportReimportMixin(object):
    def __init__(self, *args, **kwargs):
        self.scans_path = "dojo/unittests/scans/"
        self.zap_sample0_filename = self.scans_path + "zap/0_zap_sample.xml"
        self.zap_sample1_filename = (
            self.scans_path + "zap/1_zap_sample_0_and_new_absent.xml"
        )
        self.zap_sample2_filename = (
            self.scans_path + "zap/2_zap_sample_0_and_new_endpoint.xml"
        )
        self.zap_sample3_filename = (
            self.scans_path + "zap/3_zap_sampl_0_and_different_severities.xml"
        )

        self.anchore_file_name = self.scans_path + "anchore/one_vuln_many_files.json"
        self.scan_type_anchore = "Anchore Engine Scan"

    # import zap scan, testing:
    # - import
    # - active/verifed = True
    def test_zap_scan_base_active_verified(self):
        logger.debug("importing original zap xml report")

        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        # 0_zap_sample.xml: basic file with 4 out of 5 findings reported, zap4 absent
        # 1 active
        # 2 active
        # 3 active
        # 4 absent
        # 5 active

        test_id = import0["test"]
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # imported count must match count in xml report
        self.assert_finding_count_json(4, findings)

        # the zap scan contains 3 endpoints (mainsite with pot + uris from findings)
        self.assertEqual(endpoint_count_before + 3, self.db_endpoint_count())
        # 4 findings, total 11 endpoint statuses
        self.assertEqual(
            endpoint_status_count_before_active + 11,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated,
            self.db_endpoint_status_count(mitigated=True),
        )

        # no notes expected
        self.assertEqual(notes_count_before, self.db_notes_count())

        return test_id

    # import 0 and then reimport 0 again
    # - reimport, findings stay the same, stay active
    # - active = True, verified = Trie
    # - existing findings with verified is true should stay verified
    def test_import_0_reimport_0_active_verified(self):
        logger.debug("reimporting exact same original zap xml report again")

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        test_id = import0["test"]

        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        # reimport exact same report
        reimport0 = self.reimport_scan_with_params(test_id, self.zap_sample0_filename)

        test_id = reimport0["test"]
        self.assertEqual(test_id, test_id)

        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # reimported count must match count in xml report
        findings = self.get_test_findings_api(test_id)
        self.assert_finding_count_json(4, findings)

        # reimporting the exact same scan shouldn't modify the number of endpoints and statuses
        self.assertEqual(endpoint_count_before, self.db_endpoint_count())
        self.assertEqual(
            endpoint_status_count_before_active,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated,
            self.db_endpoint_status_count(mitigated=True),
        )

        # reimporting the exact same scan shouldn't create any notes
        self.assertEqual(notes_count_before, self.db_notes_count())

    # import 0 and then reimport 0 again with verified is false
    # - reimport, findings stay the same, stay active
    # - active = True, verified = False
    # - existing findings with verified is true should stay verified
    def test_import_0_reimport_0_active_not_verified(self):
        logger.debug(
            "reimporting exact same original zap xml report again, verified=False"
        )

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        test_id = import0["test"]

        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        # reimport exact same report
        reimport0 = self.reimport_scan_with_params(
            test_id, self.zap_sample0_filename, verified=False
        )

        test_id = reimport0["test"]
        self.assertEqual(test_id, test_id)

        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # reimported count must match count in xml report
        # we set verified=False in this reimport, but currently DD does not update this flag, so it's still True from previous import
        findings = self.get_test_findings_api(test_id, verified=True)
        self.assert_finding_count_json(4, findings)

        # inversely, we should see no findings with verified=False
        findings = self.get_test_findings_api(test_id, verified=False)
        self.assert_finding_count_json(0, findings)

        # reimporting the exact same scan shouldn't modify the number of endpoints
        self.assertEqual(endpoint_count_before, self.db_endpoint_count())
        self.assertEqual(
            endpoint_status_count_before_active,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated,
            self.db_endpoint_status_count(mitigated=True),
        )

        # reimporting the exact same scan shouldn't create any notes
        self.assertEqual(notes_count_before, self.db_notes_count())

    # import 0 and then reimport 1 with zap4 as extra finding, zap1 closed.
    # - active findings count should be 4
    # - total  findings count should be 5
    # - zap1 is closed, so endpoints should be mitigated
    # - verified is false, so zap4 should not be verified.
    # - existing findings with verified is true should stay verified
    def test_import_0_reimport_1_active_not_verified(self):
        logger.debug(
            "reimporting updated zap xml report, 1 new finding and 1 no longer present, verified=False"
        )

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        test_id = import0["test"]
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        finding_count_before = self.db_finding_count()
        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        # reimport updated report
        reimport1 = self.reimport_scan_with_params(
            test_id, self.zap_sample1_filename, verified=False
        )

        test_id = reimport1["test"]
        self.assertEqual(test_id, test_id)

        test = self.get_test_api(test_id)
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # active findings must be equal to those in both reports
        findings = self.get_test_findings_api(test_id)
        self.assert_finding_count_json(4 + 1, findings)

        # verified findings must be equal to those in report 0
        findings = self.get_test_findings_api(test_id, verified=True)
        self.assert_finding_count_json(4, findings)

        findings = self.get_test_findings_api(test_id, verified=False)
        self.assert_finding_count_json(1, findings)

        # the updated scan report has
        # - 1 new finding
        self.assertEqual(finding_count_before + 1, self.db_finding_count())
        # zap4 only uses 2 endpoints that already exist
        self.assertEqual(endpoint_count_before, self.db_endpoint_count())
        # but 2 statuses should be created for those endpoints, 3 statuses for zap1 closed
        self.assertEqual(
            endpoint_status_count_before_active + 2 - 3,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated + 3,
            self.db_endpoint_status_count(mitigated=True),
        )

        # - 1 new note for zap1 being closed now
        self.assertEqual(notes_count_before + 1, self.db_notes_count())

    # import 0 and then reimport 1 with zap4 as extra finding, zap1 closed and then reimport 1 again
    # - active findings count should be 4
    # - total  findings count should be 5
    # - zap1 active, zap4 inactive
    def test_import_0_reimport_1_active_verified_reimport_0_active_verified(self):
        logger.debug(
            "reimporting updated zap xml report, 1 new finding and 1 no longer present, verified=True and then 0 again"
        )

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        test_id = import0["test"]
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        finding_count_before = self.db_finding_count()
        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        reimport1 = self.reimport_scan_with_params(test_id, self.zap_sample1_filename)

        # zap1 should be closed 3 endpoint statuses less, but 2 extra for zap4
        self.assertEqual(
            endpoint_status_count_before_active - 3 + 2,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated + 3,
            self.db_endpoint_status_count(mitigated=True),
        )

        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )

        reimport0 = self.reimport_scan_with_params(test_id, self.zap_sample0_filename)

        test_id = reimport1["test"]
        self.assertEqual(test_id, test_id)

        test = self.get_test_api(test_id)
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # active findings must be equal to those in both reports
        findings = self.get_test_findings_api(test_id)
        self.assert_finding_count_json(4 + 1, findings)

        zap1_ok = False
        zap4_ok = False
        for finding in findings["results"]:
            if "Zap1" in finding["title"]:
                self.assertTrue(finding["active"])
                zap1_ok = True
            if "Zap4" in finding["title"]:
                self.assertFalse(finding["active"])
                zap4_ok = True

        self.assertTrue(zap1_ok)
        self.assertTrue(zap4_ok)

        # verified findings must be equal to those in report 0
        findings = self.get_test_findings_api(test_id, verified=True)
        self.assert_finding_count_json(4 + 1, findings)

        findings = self.get_test_findings_api(test_id, verified=False)
        self.assert_finding_count_json(0, findings)

        self.assertEqual(endpoint_count_before, self.db_endpoint_count())

        # zap4 should be closed again so 2 mitigated eps, zap1 should be open again so 3 active extra
        self.assertEqual(
            endpoint_status_count_before_active + 3 - 2,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated - 3 + 2,
            self.db_endpoint_status_count(mitigated=True),
        )

        # zap1 was closed and then opened -> 2 notes
        # zap4 was created and then closed -> only 1 note
        self.assertEqual(notes_count_before + 2 + 1, self.db_notes_count())

    # import 0 and then reimport 2 with an extra endpoint for zap1
    # - extra endpoint should be present in db
    # - reimport doesn't look at endpoints to match against existing findings
    def test_import_0_reimport_2_extra_endpoint(self):
        logger.debug(
            "reimporting exact same original zap xml report again, with an extra endpoint for zap1"
        )

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        test_id = import0["test"]
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        finding_count_before = self.db_finding_count()
        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        reimport2 = self.reimport_scan_with_params(test_id, self.zap_sample2_filename)

        test_id = reimport2["test"]
        self.assertEqual(test_id, test_id)

        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # reimported count must match count in xml report
        findings = self.get_test_findings_api(test_id)
        self.assert_finding_count_json(4, findings)

        self.assertEqual(endpoint_count_before + 1, self.db_endpoint_count())
        self.assertEqual(
            endpoint_status_count_before_active + 1,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated,
            self.db_endpoint_status_count(mitigated=True),
        )

        # reimporting the exact same scan shouldn't create any notes
        self.assertEqual(notes_count_before, self.db_notes_count())
        self.assertEqual(finding_count_before, self.db_finding_count())

    # import 0 and then reimport 2 with an extra endpoint for zap1 and then 0 again to remove the extra endpoint again
    # - extra endpoint should no long be present in db
    # - reimport doesn't look at endpoints to match against existing findings
    def test_import_0_reimport_2_extra_endpoint_reimport_0(self):
        logger.debug(
            "reimporting exact same original zap xml report again, with an extra endpoint for zap1"
        )

        # self.log_finding_summary_json_api()

        import0 = self.import_scan_with_params(self.zap_sample0_filename)
        test_id = import0["test"]
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        reimport2 = self.reimport_scan_with_params(test_id, self.zap_sample2_filename)

        test_id = reimport2["test"]
        self.assertEqual(test_id, test_id)

        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        finding_count_before = self.db_finding_count()
        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        reimport0 = self.reimport_scan_with_params(test_id, self.zap_sample0_filename)

        test_id = reimport0["test"]
        self.assertEqual(test_id, test_id)

        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        # reimported count must match count in xml report
        findings = self.get_test_findings_api(test_id)
        self.assert_finding_count_json(4, findings)

        # existing BUG: endpoint that is no longer in last scan should be removed or marked as mitigated
        self.assertEqual(endpoint_count_before, self.db_endpoint_count())
        self.assertEqual(
            endpoint_status_count_before_active,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated,
            self.db_endpoint_status_count(mitigated=True),
        )

        # reimporting the exact same scan shouldn't create any notes
        self.assertEqual(notes_count_before, self.db_notes_count())
        self.assertEqual(finding_count_before, self.db_finding_count())

    # import 0 and then reimport 3 with severities changed for zap1 and zap2
    # - reimport will match on severity, so now should create 2 new findings
    # - and close the 2 old findings because they have a different severity
    # - so zap1 + zap2 closed
    # - 2 new findings zap1' and zap2'
    def test_import_0_reimport_3_active_verified(self):
        logger.debug(
            "reimporting updated zap xml report, with different severities for zap2 and zap5"
        )

        import0 = self.import_scan_with_params(self.zap_sample0_filename)

        test_id = import0["test"]
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)

        finding_count_before = self.db_finding_count()
        endpoint_count_before = self.db_endpoint_count()
        endpoint_status_count_before_active = self.db_endpoint_status_count(
            mitigated=False
        )
        endpoint_status_count_before_mitigated = self.db_endpoint_status_count(
            mitigated=True
        )
        notes_count_before = self.db_notes_count()

        # reimport updated report
        reimport1 = self.reimport_scan_with_params(test_id, self.zap_sample3_filename)

        test_id = reimport1["test"]
        self.assertEqual(test_id, test_id)

        test = self.get_test_api(test_id)
        findings = self.get_test_findings_api(test_id)
        self.log_finding_summary_json_api(findings)
        self.assert_finding_count_json(4 + 2, findings)

        zap2_ok = False
        zap5_ok = False
        for finding in findings["results"]:
            if "Zap2" in finding["title"]:
                self.assertTrue(finding["active"] or finding["severity"] == "Low")
                self.assertTrue(
                    not finding["active"] or finding["severity"] == "Medium"
                )
                zap2_ok = True
            if "Zap5" in finding["title"]:
                self.assertTrue(finding["active"] or finding["severity"] == "Low")
                self.assertTrue(
                    not finding["active"] or finding["severity"] == "Medium"
                )
                zap5_ok = True

        self.assertTrue(zap2_ok)
        self.assertTrue(zap5_ok)

        # verified findings must be equal to those in report 0
        findings = self.get_test_findings_api(test_id, verified=True)
        self.assert_finding_count_json(4 + 2, findings)

        findings = self.get_test_findings_api(test_id, verified=False)
        self.assert_finding_count_json(0, findings)

        # the updated scan report has
        # - 2 new findings, 2 new endpoints, 3 + 3 new endpoint statuses active, 3 + 3 endpoint statues mitigated due to zap1+2 closed
        self.assertEqual(finding_count_before + 2, self.db_finding_count())
        self.assertEqual(endpoint_count_before, self.db_endpoint_count())
        self.assertEqual(
            endpoint_status_count_before_active + 3 + 3 - 3 - 3,
            self.db_endpoint_status_count(mitigated=False),
        )
        self.assertEqual(
            endpoint_status_count_before_mitigated + 3 + 3,
            self.db_endpoint_status_count(mitigated=True),
        )

        # - zap2 and zap5 closed
        self.assertEqual(notes_count_before + 2, self.db_notes_count())

    # import 1 and then reimport 2 without closing old findings
    # - reimport should not mitigate the zap1
    def test_import_reimport_without_closing_old_findings(self):
        logger.debug("reimporting updated zap xml report and keep old findings open")

        import1 = self.import_scan_with_params(self.zap_sample1_filename)

        test_id = import1["test"]
        findings = self.get_test_findings_api(test_id)
        self.assert_finding_count_json(4, findings)

        reimport1 = self.reimport_scan_with_params(
            test_id, self.zap_sample2_filename, close_old_findings=False
        )

        test_id = reimport1["test"]
        self.assertEqual(test_id, test_id)

        findings = self.get_test_findings_api(test_id, verified=False)
        self.assert_finding_count_json(0, findings)

        findings = self.get_test_findings_api(test_id, verified=True)
        self.assert_finding_count_json(5, findings)

        mitigated = 0
        not_mitigated = 0
        for finding in findings["results"]:
            logger.debug(finding)
            if finding["is_Mitigated"]:
                mitigated += 1
            else:
                not_mitigated += 1
        self.assertEqual(mitigated, 0)
        self.assertEqual(not_mitigated, 5)

    # some parsers generate 1 finding for each vulnerable file for each vulnerability
    # i.e
    # #: title                     : sev : file_path
    # 1: CVE-2020-1234 jquery      : 1   : /file1.jar
    # 2: CVE-2020-1234 jquery      : 1   : /file2.jar
    #
    # if we don't filter on file_path, we would find 2 existing findings
    # and the logic below will get confused and just create a new finding
    # and close the two existing ones. including and duplicates.
    #
    def test_import_0_reimport_0_anchore_file_path(self):
        import0 = self.import_scan_with_params(
            self.anchore_file_name, scan_type=self.scan_type_anchore
        )

        test_id = import0["test"]

        active_findings_before = self.get_test_findings_api(test_id, active=True)
        self.log_finding_summary_json_api(active_findings_before)

        active_findings_count_before = active_findings_before["count"]
        notes_count_before = self.db_notes_count()

        # reimport exact same report
        reimport0 = self.reimport_scan_with_params(
            test_id, self.anchore_file_name, scan_type=self.scan_type_anchore
        )

        active_findings_after = self.get_test_findings_api(test_id, active=True)
        self.log_finding_summary_json_api(active_findings_after)
        self.assert_finding_count_json(
            active_findings_count_before, active_findings_after
        )

        # reimporting the exact same scan shouldn't create any notes
        self.assertEqual(notes_count_before, self.db_notes_count())


class ImportReimportTestAPI(DojoAPITestCase, ImportReimportMixin):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        # TODO remove __init__ if it does nothing...
        ImportReimportMixin.__init__(self, *args, **kwargs)
        # super(ImportReimportMixin, self).__init__(*args, **kwargs)
        # super(DojoAPITestCase, self).__init__(*args, **kwargs)
        super().__init__(*args, **kwargs)

    def setUp(self):
        testuser = User.objects.get(username="admin")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        # self.url = reverse(self.viewname + '-list')


class ImportReimportTestUI(DojoAPITestCase, ImportReimportMixin):
    fixtures = ["dojo_testdata.json"]
    client_ui = Client()

    def __init__(self, *args, **kwargs):
        # TODO remove __init__ if it does nothing...
        ImportReimportMixin.__init__(self, *args, **kwargs)
        # super(ImportReimportMixin, self).__init__(*args, **kwargs)
        # super(DojoAPITestCase, self).__init__(*args, **kwargs)
        super().__init__(*args, **kwargs)

    def setUp(self):
        # still using the API to verify results
        testuser = User.objects.get(username="admin")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        # self.url = reverse(self.viewname + '-list')

        self.client_ui = Client()
        self.client_ui.force_login(self.get_test_admin())

    # override methods to use UI
    def import_scan_with_params(self, *args, **kwargs):
        return self.import_scan_with_params_ui(*args, **kwargs)

    def reimport_scan_with_params(self, *args, **kwargs):
        return self.reimport_scan_with_params_ui(*args, **kwargs)

    def import_scan_ui(self, engagement, payload):
        logger.debug("import_scan payload %s", payload)
        # response = self.client_ui.post(reverse('import_scan_results', args=(engagement, )), urlencode(payload), content_type='application/x-www-form-urlencoded')
        response = self.client_ui.post(
            reverse("import_scan_results", args=(engagement,)), payload
        )
        # print(vars(response))
        print("url: " + response.url)
        test = Test.objects.get(id=response.url.split("/")[-1])
        # f = open('response.html', 'w+')
        # f.write(str(response.content, 'utf-8'))
        # f.close()
        self.assertEqual(302, response.status_code, response.content[:1000])
        return {"test": test.id}

    def reimport_scan_ui(self, test, payload):
        response = self.client_ui.post(
            reverse("re_import_scan_results", args=(test,)), payload
        )
        self.assertEqual(302, response.status_code, response.content[:1000])
        test = Test.objects.get(id=response.url.split("/")[-1])
        return {"test": test.id}

    def import_scan_with_params_ui(
        self,
        filename,
        scan_type="ZAP Scan",
        engagement=1,
        minimum_severity="Low",
        active=True,
        verified=True,
        push_to_jira=None,
        tags=None,
        close_old_findings=False,
    ):
        payload = {
            "scan_date": "2020-06-04",
            "minimum_severity": minimum_severity,
            "active": active,
            "verified": verified,
            "scan_type": scan_type,
            "file": open(filename),
            "environment": 1
            # "version": "1.0.1",
            # "close_old_findings": close_old_findings,
        }

        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        if tags is not None:
            payload["tags"] = tags

        return self.import_scan_ui(engagement, payload)

    def reimport_scan_with_params_ui(
        self,
        test_id,
        filename,
        scan_type="ZAP Scan",
        minimum_severity="Low",
        active=True,
        verified=True,
        push_to_jira=None,
        tags=None,
        close_old_findings=True,
    ):
        payload = {
            "scan_date": "2020-06-04",
            "minimum_severity": minimum_severity,
            "active": active,
            "verified": verified,
            "scan_type": scan_type,
            "file": open(filename),
            "version": "1.0.1",
            "close_old_findings": close_old_findings,
        }

        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        if tags is not None:
            payload["tags"] = tags

        return self.reimport_scan_ui(test_id, payload)


# Observations:
# - When reopening a mitigated finding, almost no fields are updated such as title, description, severity, impact, references, ....
# - Basically fields (and req/resp) are only stored on the initial import, reimporting only changes the active/mitigated/verified flags + some dates + notes
# - (Re)Import could provide some more statistics of imported findings (reimport: new, mitigated, reactivated, untouched, ...)
# - Endpoints that are no longer present in the scan that is imported, are still retained by DD, which makes them look "active" in the product view
# - Maybe test severity threshold?
# - Not sure,but I doubt the Endpoint_Status objects are created at all during import/reimport? Or are those not needed?
