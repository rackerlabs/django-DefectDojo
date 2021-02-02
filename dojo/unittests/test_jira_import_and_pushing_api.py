from dojo.models import User, Finding, JIRA_Instance
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APIClient
from .dojo_test_case import DojoVCRAPITestCase

# from unittest import skip
import logging
from vcr import VCR


logger = logging.getLogger(__name__)

# these tests are using vcrpy to record traffic to and from JIRA: https://vcrpy.readthedocs.io/en/latest/usage.html
# after being recorded, the traffic is used for future runs of the tests
# this allows us to locally develop tests, run them, make them work against a real JIRA instance.
# after that we can commit the tests AND the recordings (cassettes).

# the record_mode is set to 'once' by default. this means it will replay responses from the cassette, if there is a cassette.
# otherwise it will create a new cassette and record responses. on the next run the cassette wil be used.

# if changing tests, you can best remove all cassettes before running the tests.
# or you can temporarily set the record_mode to all the make it always go to the real JIRA and record all the traffic.

# when the tests are finished, you'll have to set the assertCassettePlayed method to make it assert
# that all entries in the cassette have been used by the test.

# if you need some credentials for the Defect Dojo JIRA Cloud instance, contact one of the moderators

# some senstive data is filtered out by the filter_headers config option below
# as well as some custom callback functions to filter out cookies.
# please check the recorded files on sensitive data before committing to git


# filters headers doesn't seem to work for cookies, so use callbacks to filter cookies from being recorded
# https://github.com/kevin1024/vcrpy/issues/569
def before_record_request(request):
    if "Cookie" in request.headers:
        del request.headers["Cookie"]
    if "cookie" in request.headers:
        del request.headers["cookie"]
    return request


def before_record_response(response):
    if "Set-Cookie" in response["headers"]:
        del response["headers"]["Set-Cookie"]
    if "set-cookie" in response["headers"]:
        del response["headers"]["set-cookie"]
    return response


class JIRAConfigAndPushTestApi(DojoVCRAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        # TODO remove __init__ if it does nothing...
        APITestCase.__init__(self, *args, **kwargs)

    def assert_cassette_played(self):
        if (
            True
        ):  # set to True when committing. set to False when recording new test cassettes
            self.assertTrue(self.cassette.all_played)

    def _get_vcr(self, **kwargs):
        my_vcr = super(JIRAConfigAndPushTestApi, self)._get_vcr(**kwargs)
        my_vcr.record_mode = "once"
        my_vcr.path_transformer = VCR.ensure_suffix(".yaml")
        my_vcr.filter_headers = ["Authorization", "X-Atlassian-Token"]
        my_vcr.cassette_library_dir = "dojo/unittests/vcr/jira/"
        # filters headers doesn't seem to work for cookies, so use callbacks to filter cookies from being recorded
        my_vcr.before_record_request = before_record_request
        my_vcr.before_record_response = before_record_response
        return my_vcr

    def setUp(self):
        super().setUp()
        self.system_settings(enable_jira=True)
        testuser = User.objects.get(username="admin")
        testuser.usercontactinfo.block_execution = True
        testuser.usercontactinfo.save()
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        self.scans_path = "dojo/unittests/scans/zap/"
        self.zap_sample5_filename = self.scans_path + "5_zap_sample_one.xml"

    def test_import_no_push_to_jira(self):
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 0)
        return test_id

    def test_import_with_push_to_jira_is_false(self):
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=False
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 0)
        return test_id

    def test_import_with_push_to_jira(self):
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=True
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_with_push_to_jira_epic(self):
        jira_instance = JIRA_Instance.objects.get(id=2)
        # we choose issue type Epic and test if it can be created succesfully.
        # if yes, it means we have succesfully populated the Epic Name custom field which is mandatory in JIRA
        jira_instance.default_issue_type = "Epic"
        jira_instance.save()
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=True
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_no_push_to_jira_but_push_all(self):
        self.set_jira_push_all_issues(self.get_engagement(1))
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_with_push_to_jira_is_false_but_push_all(self):
        self.set_jira_push_all_issues(self.get_engagement(1))
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=False
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_no_push_to_jira_reimport_no_push_to_jira(self):
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 0)

        reimport = self.reimport_scan_with_params(test_id, self.zap_sample5_filename)
        self.assert_jira_issue_count_in_test(test_id, 0)
        return test_id

    def test_import_no_push_to_jira_reimport_push_to_jira_false(self):
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 0)

        reimport = self.reimport_scan_with_params(
            test_id, self.zap_sample5_filename, push_to_jira=False
        )
        self.assert_jira_issue_count_in_test(test_id, 0)
        return test_id

    def test_import_no_push_to_jira_reimport_with_push_to_jira(self):
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 0)

        reimport = self.reimport_scan_with_params(
            test_id, self.zap_sample5_filename, push_to_jira=True
        )
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_no_push_to_jira_reimport_no_push_to_jira_but_push_all_issues(self):
        self.set_jira_push_all_issues(self.get_engagement(1))
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)

        reimport = self.reimport_scan_with_params(test_id, self.zap_sample5_filename)
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_no_push_to_jira_reimport_push_to_jira_is_false_but_push_all_issues(
        self,
    ):
        self.set_jira_push_all_issues(self.get_engagement(1))
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)

        reimport = self.reimport_scan_with_params(
            test_id, self.zap_sample5_filename, push_to_jira=False
        )
        self.assert_jira_issue_count_in_test(test_id, 2)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_push_to_jira_reimport_with_push_to_jira(self):
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=True
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)
        # Get one of the findings from the test
        finding_id = Finding.objects.filter(test__id=test_id).first().id
        pre_jira_status = self.get_jira_issue_severity(finding_id)
        # re-import and see status change
        reimport = self.reimport_scan_with_params(
            test_id, self.zap_sample5_filename, push_to_jira=True
        )
        self.assert_jira_issue_count_in_test(test_id, 2)
        post_jira_status = self.get_jira_issue_severity(finding_id)
        self.assert_jira_status_change(pre_jira_status, post_jira_status)
        # by asserting full cassette is played we know issues have been updated in JIRA
        self.assert_cassette_played()
        return test_id

    def test_import_twice_push_to_jira(self):
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=True
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)

        import1 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=True
        )
        test_id1 = import1["test"]
        # duplicates shouldn't be sent to JIRA
        self.assert_jira_issue_count_in_test(test_id1, 0)

    def test_import_twice_push_to_jira_push_all_issues(self):
        self.set_jira_push_all_issues(self.get_engagement(1))
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)

        import1 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id1 = import1["test"]
        # duplicates shouldn't be sent to JIRA
        self.assert_jira_issue_count_in_test(test_id1, 0)

    def test_create_edit_update_finding_no_push_to_jira(self):
        import0 = self.import_scan_with_params(self.zap_sample5_filename)
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 0)

        findings = self.get_test_findings_api(test_id)

        finding_id = findings["results"][0]["id"]
        # logger.debug('finding_id: %s', finding_id)

        # use existing finding as template, but change some fields to make it not a duplicate
        finding_details = self.get_finding_api(finding_id)
        del finding_details["id"]
        del finding_details["push_to_jira"]

        finding_details["title"] = "jira api test 1"
        self.post_new_finding_api(finding_details)
        self.assert_jira_issue_count_in_test(test_id, 0)

        finding_details["title"] = "jira api test 2"
        self.post_new_finding_api(finding_details, push_to_jira=True)
        self.assert_jira_issue_count_in_test(test_id, 1)

        finding_details["title"] = "jira api test 3"
        new_finding_json = self.post_new_finding_api(finding_details)
        self.assert_jira_issue_count_in_test(test_id, 1)

        self.patch_finding_api(new_finding_json["id"], {"push_to_jira": False})
        self.assert_jira_issue_count_in_test(test_id, 1)
        self.patch_finding_api(new_finding_json["id"], {"push_to_jira": True})
        self.assert_jira_issue_count_in_test(test_id, 2)
        pre_jira_status = self.get_jira_issue_severity(new_finding_json["id"])

        self.patch_finding_api(
            new_finding_json["id"],
            {"push_to_jira": True, "is_Mitigated": True, "active": False},
        )
        self.assert_jira_issue_count_in_test(test_id, 2)
        post_jira_status = self.get_jira_issue_severity(new_finding_json["id"])
        self.assert_jira_status_change(pre_jira_status, post_jira_status)

        finding_details["title"] = "jira api test 4"
        new_finding_json = self.post_new_finding_api(finding_details)
        new_finding_id = new_finding_json["id"]
        del new_finding_json["id"]

        self.assert_jira_issue_count_in_test(test_id, 2)
        self.put_finding_api(new_finding_id, new_finding_json, push_to_jira=False)
        self.assert_jira_issue_count_in_test(test_id, 2)
        self.put_finding_api(new_finding_id, new_finding_json, push_to_jira=True)
        self.assert_jira_issue_count_in_test(test_id, 3)
        self.put_finding_api(new_finding_id, new_finding_json, push_to_jira=True)
        self.assert_jira_issue_count_in_test(test_id, 3)

        self.assert_cassette_played()

    def test_import_with_push_to_jira_add_comment(self):
        import0 = self.import_scan_with_params(
            self.zap_sample5_filename, push_to_jira=True
        )
        test_id = import0["test"]
        self.assert_jira_issue_count_in_test(test_id, 2)

        findings = self.get_test_findings_api(test_id)

        finding_id = findings["results"][0]["id"]

        response = self.post_finding_notes_api(
            finding_id, "testing note. creating it and pushing it to JIRA"
        )

        # by asserting full cassette is played we know all calls to JIRA have been made as expected
        self.assert_cassette_played()
        return test_id
