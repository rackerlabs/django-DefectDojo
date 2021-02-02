from dojo.models import (
    Product,
    Engagement,
    Test,
    Finding,
    JIRA_Issue,
    Tool_Product_Settings,
    Tool_Configuration,
    Tool_Type,
    User,
    ScanSettings,
    Scan,
    Stub_Finding,
    Endpoint,
    JIRA_Project,
    JIRA_Instance,
    Finding_Template,
    Note_Type,
    App_Analysis,
    Endpoint_Status,
    Sonarqube_Issue,
    Sonarqube_Issue_Transition,
    Sonarqube_Product,
    Notes,
    BurpRawRequestResponse,
    DojoMeta,
    FileUpload,
)
from dojo.api_v2.views import (
    EndPointViewSet,
    EngagementViewSet,
    FindingTemplatesViewSet,
    FindingViewSet,
    JiraInstanceViewSet,
    JiraIssuesViewSet,
    JiraProjectViewSet,
    ProductViewSet,
    ScanSettingsViewSet,
    ScansViewSet,
    StubFindingsViewSet,
    TestsViewSet,
    ToolConfigurationsViewSet,
    ToolProductSettingsViewSet,
    ToolTypesViewSet,
    UsersViewSet,
    ImportScanView,
    NoteTypeViewSet,
    AppAnalysisViewSet,
    EndpointStatusViewSet,
    SonarqubeIssueViewSet,
    NotesViewSet,
)
from json import dumps
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .dojo_test_case import DojoAPITestCase
from dojo.api_v2.prefetch.utils import _get_prefetchable_fields
from rest_framework.mixins import (
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    DestroyModelMixin,
    UpdateModelMixin,
)
from dojo.api_v2.prefetch import PrefetchListMixin, PrefetchRetrieveMixin
import logging
import pathlib


logger = logging.getLogger(__name__)


def skipIfNotSubclass(baseclass):
    def decorate(f):
        def wrapper(self, *args, **kwargs):
            if not issubclass(self.viewset, baseclass):
                self.skipTest("This view does not inherit from %s" % baseclass)
            else:
                f(self, *args, **kwargs)

        return wrapper

    return decorate


class BaseClass:
    class RESTEndpointTest(DojoAPITestCase):
        def __init__(self, *args, **kwargs):
            DojoAPITestCase.__init__(self, *args, **kwargs)

        def setUp(self):
            testuser = User.objects.get(username="admin")
            token = Token.objects.get(user=testuser)
            self.client = APIClient()
            self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
            self.url = reverse(self.viewname + "-list")

        @skipIfNotSubclass(ListModelMixin)
        def test_list(self):
            check_for_tags = False
            if (
                hasattr(self.endpoint_model, "tags")
                and self.payload
                and self.payload.get("tags", None)
            ):
                # create a new instance first to make sure there's at least 1 instance with tags set by payload to trigger tag handling code
                logger.debug("creating model with endpoints: %s", self.payload)
                response = self.client.post(self.url, self.payload)
                self.assertEqual(201, response.status_code, response.content[:1000])

                # print('response:', response.content[:1000])
                check_for_id = response.data["id"]
                # print('id: ', check_for_id)
                check_for_tags = self.payload.get("tags", None)

            response = self.client.get(self.url, format="json")
            # tags must be present in last entry, the one we created
            if check_for_tags:
                tags_found = False
                for result in response.data["results"]:
                    if result["id"] == check_for_id:
                        # logger.debug('result.tags: %s', result.get('tags', ''))
                        self.assertEqual(
                            len(check_for_tags), len(result.get("tags", None))
                        )
                        for tag in check_for_tags:
                            # logger.debug('looking for tag %s in tag list %s', tag, result['tags'])
                            self.assertTrue(tag in result["tags"])
                        tags_found = True
                self.assertTrue(tags_found)

            self.assertEqual(200, response.status_code, response.content[:1000])

        @skipIfNotSubclass(CreateModelMixin)
        def test_create(self):
            length = self.endpoint_model.objects.count()
            response = self.client.post(self.url, self.payload)
            logger.debug("test_create_response:")
            logger.debug(response)
            logger.debug(response.data)
            self.assertEqual(201, response.status_code, response.content[:1000])
            self.assertEqual(self.endpoint_model.objects.count(), length + 1)

            if (
                hasattr(self.endpoint_model, "tags")
                and self.payload
                and self.payload.get("tags", None)
            ):
                self.assertEqual(
                    len(self.payload.get("tags")), len(response.data.get("tags", None))
                )
                for tag in self.payload.get("tags"):
                    # logger.debug('looking for tag %s in tag list %s', tag, response.data['tags'])
                    self.assertTrue(tag in response.data["tags"])

        @skipIfNotSubclass(RetrieveModelMixin)
        def test_detail(self):
            current_objects = self.client.get(self.url, format="json").data
            relative_url = self.url + "%s/" % current_objects["results"][0]["id"]
            response = self.client.get(relative_url)
            self.assertEqual(200, response.status_code, response.content[:1000])
            # sensitive data must be set to write_only so those are not returned in the response
            # https://github.com/DefectDojo/django-DefectDojo/security/advisories/GHSA-8q8j-7wc4-vjg5
            self.assertFalse("password" in response.data)
            self.assertFalse("ssh" in response.data)
            self.assertFalse("api_key" in response.data)

        @skipIfNotSubclass(DestroyModelMixin)
        def test_delete(self):
            current_objects = self.client.get(self.url, format="json").data
            relative_url = self.url + "%s/" % current_objects["results"][0]["id"]
            response = self.client.delete(relative_url)
            self.assertEqual(204, response.status_code, response.content[:1000])

        @skipIfNotSubclass(UpdateModelMixin)
        def test_update(self):
            current_objects = self.client.get(self.url, format="json").data
            relative_url = self.url + "%s/" % current_objects["results"][0]["id"]
            response = self.client.patch(relative_url, self.update_fields)

            self.assertEqual(200, response.status_code, response.content[:1000])

            for key, value in self.update_fields.items():
                # some exception as push_to_jira has been implemented strangely in the update methods in the api
                if key not in ["push_to_jira", "ssh", "password", "api_key"]:
                    self.assertEqual(value, response.data[key])

            self.assertFalse("push_to_jira" in response.data)
            self.assertFalse("ssh" in response.data)
            self.assertFalse("password" in response.data)
            self.assertFalse("api_key" in response.data)

            if (
                hasattr(self.endpoint_model, "tags")
                and self.update_fields
                and self.update_fields.get("tags", None)
            ):
                self.assertEqual(
                    len(self.update_fields.get("tags")),
                    len(response.data.get("tags", None)),
                )
                for tag in self.update_fields.get("tags"):
                    logger.debug(
                        "looking for tag %s in tag list %s", tag, response.data["tags"]
                    )
                    self.assertTrue(tag in response.data["tags"])

            response = self.client.put(relative_url, self.payload)
            self.assertEqual(200, response.status_code, response.content[:1000])

        @skipIfNotSubclass(PrefetchRetrieveMixin)
        def test_detail_prefetch(self):
            print("=======================================================")
            prefetchable_fields = [
                x[0] for x in _get_prefetchable_fields(self.viewset.serializer_class)
            ]

            current_objects = self.client.get(self.url, format="json").data
            relative_url = self.url + "%s/" % current_objects["results"][0]["id"]
            response = self.client.get(
                relative_url, data={"prefetch": ",".join(prefetchable_fields)}
            )

            self.assertEqual(200, response.status_code)
            obj = response.data
            self.assertTrue("prefetch" in obj)

            for field in prefetchable_fields:
                field_value = obj.get(field, None)
                if field_value is None:
                    continue

                self.assertTrue(field in obj["prefetch"])
                values = field_value if type(field_value) is list else [field_value]

                for value in values:
                    self.assertTrue(value in obj["prefetch"][field])

        @skipIfNotSubclass(PrefetchListMixin)
        def test_list_prefetch(self):
            prefetchable_fields = [
                x[0] for x in _get_prefetchable_fields(self.viewset.serializer_class)
            ]

            response = self.client.get(
                self.url, data={"prefetch": ",".join(prefetchable_fields)}
            )

            self.assertEqual(200, response.status_code)
            objs = response.data
            self.assertTrue("results" in objs)
            self.assertTrue("prefetch" in objs)

            for obj in objs["results"]:
                for field in prefetchable_fields:
                    field_value = obj.get(field, None)
                    if field_value is None:
                        continue

                    self.assertTrue(field in objs["prefetch"])
                    values = field_value if type(field_value) is list else [field_value]

                    for value in values:
                        if type(value) is not int:
                            value = value["id"]
                        self.assertTrue(value in objs["prefetch"][field])


class AppAnalysisTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = App_Analysis
        self.viewname = "app_analysis"
        self.viewset = AppAnalysisViewSet
        self.payload = {
            "product": 1,
            "name": "Tomcat",
            "user": 1,
            "confidence": 100,
            "version": "8.5.1",
            "icon": "",
            "website": "",
            "website_found": "",
            "created": "2018-08-16T16:58:23.908Z",
        }
        self.update_fields = {"version": "9.0"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class EndpointStatusTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Endpoint_Status
        self.viewname = "endpoint_status"
        self.viewset = EndpointStatusViewSet
        self.payload = {
            "endpoint": 2,
            "finding": 2,
            "mitigated": False,
            "false_positive": False,
            "risk_accepted": False,
            "out_of_scope": False,
            "date": "2017-01-12T00:00",
        }
        self.update_fields = {"mitigated": True}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class EndpointTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Endpoint
        self.viewname = "endpoint"
        self.viewset = EndPointViewSet
        self.payload = {
            "protocol": "http",
            "host": "127.0.0.1",
            "path": "/",
            "query": "test=true",
            "fragment": "test-1",
            "product": 1,
            "tags": ["mytag", "yourtag"],
        }
        self.update_fields = {"protocol": "ftp", "tags": ["one_new_tag"]}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class EngagementTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Engagement
        self.viewname = "engagement"
        self.viewset = EngagementViewSet
        self.payload = {
            "eng_type": 1,
            "report_type": 1,
            "name": "",
            "description": "",
            "version": "",
            "target_start": "1937-01-01",
            "target_end": "1937-01-01",
            "reason": "",
            "test_strategy": "",
            "product": "1",
            "tags": ["mytag"],
        }
        self.update_fields = {"version": "latest"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class FindingRequestResponseTest(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="admin")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_request_response_post(self):
        length = BurpRawRequestResponse.objects.count()
        payload = {"req_resp": [{"request": "POST", "response": "200"}]}
        response = self.client.post(
            "/api/v2/findings/7/request_response/",
            dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content[:1000])
        self.assertEqual(BurpRawRequestResponse.objects.count(), length + 1)

    def test_request_response_get(self):
        response = self.client.get(
            "/api/v2/findings/7/request_response/", format="json"
        )
        self.assertEqual(200, response.status_code, response.content[:1000])


class FindingFilesTest(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="admin")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_request_response_post(self):
        url_levels = ["findings/7", "tests/3", "engagements/1"]
        path = pathlib.Path(__file__).parent.absolute()
        print(path)
        for level in url_levels:
            length = FileUpload.objects.count()
            payload = {
                "title": level,
                "file": open(str(path) + "/scans/acunetix/one_finding.xml"),
            }
            response = self.client.post("/api/v2/" + level + "/files/", payload)
            self.assertEqual(200, response.status_code, response.data)
            self.assertEqual(FileUpload.objects.count(), length + 1)

    def test_request_response_get(self):
        url_levels = ["findings/7", "tests/3", "engagements/1"]
        for level in url_levels:
            response = self.client.get("/api/v2/" + level + "/files/")
            self.assertEqual(200, response.status_code)


class FindingsTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Finding
        self.viewname = "finding"
        self.viewset = FindingViewSet
        self.payload = {
            "review_requested_by": 2,
            "reviewers": [2, 3],
            "defect_review_requested_by": 2,
            "test": 3,
            "url": "http://www.example.com",
            "thread_id": 1,
            "found_by": [],
            "title": "DUMMY FINDING",
            "date": "2020-05-20",
            "cwe": 1,
            "severity": "HIGH",
            "description": "TEST finding",
            "mitigation": "MITIGATION",
            "impact": "HIGH",
            "references": "",
            "reporter": 3,
            "is_template": False,
            "active": False,
            "verified": False,
            "false_p": False,
            "duplicate": False,
            "out_of_scope": False,
            "under_review": False,
            "under_defect_review": False,
            "numerical_severity": "S0",
            "line": 100,
            "file_path": "",
            "static_finding": False,
            "dynamic_finding": False,
            "endpoints": [1, 2],
            "images": [],
            "tags": ["tag1", "tag_2"],
        }
        self.update_fields = {
            "active": True,
            "push_to_jira": "True",
            "tags": ["finding_tag_new"],
        }
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)

    def test_duplicate(self):
        # Reassign duplicate
        result = self.client.post(self.url + "2/original/3/")
        assert result.status_code == status.HTTP_200_OK, "Could not move duplicate"
        result = self.client.get(self.url + "2/")
        assert result.status_code == status.HTTP_200_OK, "Could not check new duplicate"
        result_json = result.json()
        assert result_json["duplicate"]
        assert result_json["duplicate_finding"] == 3

        # Check duplicate status
        result = self.client.get(self.url + "3/duplicate/")
        assert (
            result.status_code == status.HTTP_200_OK
        ), "Could not check duplicate status"
        result_json = result.json()
        # Should return all duplicates for id=3
        assert set(x["id"] for x in result_json) == {2, 4, 5, 6}

        # Reset duplicate
        result = self.client.post(self.url + "2/duplicate/reset/")
        assert result.status_code == status.HTTP_200_OK, "Could not reset duplicate"
        new_result = self.client.get(self.url + "2/")
        assert (
            result.status_code == status.HTTP_200_OK
        ), "Could not check reset duplicate status"
        result_json = new_result.json()
        assert not result_json["duplicate"]
        assert result_json["duplicate_finding"] is None


class FindingMetadataTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Finding
        self.viewname = "finding"
        self.viewset = FindingViewSet
        self.payload = {}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)

    def setUp(self):
        testuser = User.objects.get(username="admin")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        self.url = reverse(self.viewname + "-list")

        self.current_findings = self.client.get(self.url, format="json").data["results"]
        finding = Finding.objects.get(id=self.current_findings[0]["id"])

        self.base_url = f"{self.url}{self.current_findings[0]['id']}/metadata/"
        metadata = DojoMeta(finding=finding, name="test_meta", value="20")
        metadata.save()

    def test_create(self):
        self.client.post(self.base_url, data={"name": "test_meta2", "value": "40"})
        results = self.client.get(self.base_url).data
        for result in results:
            if result["name"] == "test_meta2" and result["value"] == "40":
                return

        assert False, "Metadata was not created correctly"

    def test_create_duplicate(self):
        result = self.client.post(
            self.base_url, data={"name": "test_meta", "value": "40"}
        )
        assert (
            result.status_code == status.HTTP_400_BAD_REQUEST
        ), "Metadata creation did not failed on duplicate"

    def test_get(self):
        results = self.client.get(self.base_url, format="json").data
        for result in results:
            if result["name"] == "test_meta" and result["value"] == "20":
                return

        assert False, "Metadata was not created correctly"

    def test_update(self):
        self.client.put(
            self.base_url + "?name=test_meta", data={"name": "test_meta", "value": "40"}
        )
        result = self.client.get(self.base_url).data[0]
        assert (
            result["name"] == "test_meta" and result["value"] == "40"
        ), "Metadata not edited correctly"

    def test_delete(self):
        self.client.delete(self.base_url + "?name=test_meta")
        result = self.client.get(self.base_url).data
        assert len(result) == 0, "Metadata not deleted correctly"


class FindingTemplatesTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Finding_Template
        self.viewname = "finding_template"
        self.viewset = FindingTemplatesViewSet
        self.payload = {
            "title": "Test template",
            "cwe": 0,
            "severity": "MEDIUM",
            "description": "test template",
            "mitigation": "None",
            "impact": "MEDIUM",
            "references": "",
        }
        self.update_fields = {"references": "some reference"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class JiraInstancesTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = JIRA_Instance
        self.viewname = "jira_instance"
        self.viewset = JiraInstanceViewSet
        self.payload = {
            "url": "http://www.example.com",
            "username": "testuser",
            "password": "testuser",
            "default_issue_type": "Story",
            "epic_name_id": 1111,
            "open_status_key": 111,
            "close_status_key": 111,
            "info_mapping_severity": "LOW",
            "low_mapping_severity": "LOW",
            "medium_mapping_severity": "LOW",
            "high_mapping_severity": "LOW",
            "critical_mapping_severity": "LOW",
            "finding_text": "",
            "global_jira_sla_notification": False,
        }
        self.update_fields = {"epic_name_id": 1}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class JiraIssuesTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = JIRA_Issue
        self.viewname = "jira_issue"
        self.viewset = JiraIssuesViewSet
        self.payload = {
            "jira_id": "JIRA 1",
            "jira_key": "SOME KEY",
            "finding": 2,
            "engagement": 2,
        }
        self.update_fields = {"finding": 2}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class JiraProjectTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = JIRA_Project
        self.viewname = "jira_project"
        self.viewset = JiraProjectViewSet
        self.payload = {
            "project_key": "TEST KEY",
            "component": "",
            "push_all_issues": False,
            "enable_engagement_epic_mapping": False,
            "push_notes": False,
            "product": 1,
            "jira_instance": 2,
        }
        self.update_fields = {"jira_instance": 3}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class SonarqubeIssueTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Sonarqube_Issue
        self.viewname = "sonarqube_issue"
        self.viewset = SonarqubeIssueViewSet
        self.payload = {
            "key": "AREwS5n5TxsFUNm31CxP",
            "status": "OPEN",
            "type": "VULNERABILITY",
        }
        self.update_fields = {"key": "AREwS5n5TxsFUNm31CxP"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class SonarqubeIssuesTransitionTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Sonarqube_Issue_Transition
        self.viewname = "sonarqube_issue_transition"
        self.viewset = SonarqubeIssuesTransitionTest
        self.payload = {
            "sonarqube_issue": 1,
            "finding_status": "Active, Verified",
            "sonarqube_status": "OPEN",
            "transitions": "confirm",
        }
        self.update_fields = {"sonarqube_status": "CLOSED"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class SonarqubeProductTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Sonarqube_Product
        self.viewname = "sonarqube_product"
        self.viewset = JiraProjectViewSet
        self.payload = {
            "product": 2,
            "sonarqube_project_key": "dojo_sonar_key",
            "sonarqube_tool_config": 3,
        }
        self.update_fields = {"sonarqube_tool_config": 2}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ProductTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Product
        self.viewname = "product"
        self.viewset = ProductViewSet
        self.payload = {
            "product_manager": 2,
            "technical_contact": 3,
            "team_manager": 2,
            "authorized_users": [2, 3],
            "prod_type": 1,
            "name": "Test Product",
            "description": "test product",
            "tags": ["mytag, yourtag"],
        }
        self.update_fields = {"prod_type": 2}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ScanSettingsTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = ScanSettings
        self.viewname = "scansettings"
        self.viewset = ScanSettingsViewSet
        self.payload = {
            "addresses": "127.0.0.1",
            "frequency": "Weekly",
            "email": "test@dojo.com",
            "protocol": "TCP",
            "product": 1,
            "user": 3,
        }
        self.update_fields = {"protocol": "ftp"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ScansTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Scan
        self.viewname = "scan"
        self.viewset = ScansViewSet
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class StubFindingsTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Stub_Finding
        self.viewname = "stub_finding"
        self.viewset = StubFindingsViewSet
        self.payload = {
            "title": "Stub Finding 1",
            "date": "2017-12-31",
            "severity": "HIGH",
            "description": "test stub finding",
            "reporter": 3,
            "test": 3,
        }
        self.update_fields = {"severity": "LOW"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class TestsTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Test
        self.viewname = "test"
        self.viewset = TestsViewSet
        self.payload = {
            "test_type": 1,
            "environment": 1,
            "engagement": 2,
            "estimated_time": "0:30:20",
            "actual_time": "0:20:30",
            "notes": [],
            "target_start": "2017-01-12T00:00",
            "target_end": "2017-01-12T00:00",
            "percent_complete": 0,
            "lead": 2,
            "tags": [],
        }
        self.update_fields = {"percent_complete": 100}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ToolConfigurationsTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Tool_Configuration
        self.viewname = "tool_configuration"
        self.viewset = ToolConfigurationsViewSet
        self.payload = {
            "configuration_url": "http://www.example.com",
            "name": "Tool Configuration",
            "description": "",
            "authentication_type": "API",
            "username": "",
            "password": "",
            "auth_title": "",
            "ssh": "",
            "api_key": "test key",
            "tool_type": 1,
        }
        self.update_fields = {"ssh": "test string"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ToolProductSettingsTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Tool_Product_Settings
        self.viewname = "tool_product_settings"
        self.viewset = ToolProductSettingsViewSet
        self.payload = {
            "setting_url": "http://www.example.com",
            "name": "Tool Product Setting",
            "description": "test tool product setting",
            "tool_project_id": "1",
            "tool_configuration": 3,
        }
        self.update_fields = {"tool_project_id": "2"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ToolTypesTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Tool_Type
        self.viewname = "tool_type"
        self.viewset = ToolTypesViewSet
        self.payload = {"name": "Tool Type", "description": "test tool type"}
        self.update_fields = {"description": "changed description"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class NoteTypesTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Note_Type
        self.viewname = "note_type"
        self.viewset = NoteTypeViewSet
        self.payload = {
            "name": "Test Note",
            "description": "not that much",
            "is_single": False,
            "is_active": True,
            "is_mandatory": False,
        }
        self.update_fields = {"description": "changed description"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class NotesTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Notes
        self.viewname = "notes"
        self.viewset = NotesViewSet
        self.payload = {
            "id": 1,
            "entry": "updated_entry",
            "author": '{"username": "admin"}',
            "editor": '{"username": "user1"}',
        }
        self.update_fields = {"entry": "changed entry"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class UsersTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = User
        self.viewname = "user"
        self.viewset = UsersViewSet
        self.payload = {
            "username": "test_user",
            "first_name": "test",
            "last_name": "user",
            "email": "example@email.com",
            "is_active": True,
        }
        self.update_fields = {"first_name": "test changed"}
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ProductPermissionTest(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="user1")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_user_should_not_have_access_to_product_3_in_list(self):
        response = self.client.get(reverse("product-list"), format="json")
        for obj in response.data["results"]:
            self.assertNotEqual(obj["id"], 3)

    def test_user_should_not_have_access_to_product_3_in_detail(self):
        response = self.client.get("http://testserver/api/v2/products/3/")
        self.assertEqual(response.status_code, 404)


class ScanSettingsPermissionTest(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="user1")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_user_should_not_have_access_to_setting_3_in_list(self):
        response = self.client.get(reverse("scansettings-list"), format="json")
        for obj in response.data["results"]:
            self.assertNotEqual(obj["id"], 3)

    def test_user_should_not_have_access_to_setting_3_in_detail(self):
        response = self.client.get("http://testserver/api/v2/scan_settings/3/")
        self.assertEqual(response.status_code, 404)


class ScansPermissionTest(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="user1")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_user_should_not_have_access_to_scan_3_in_list(self):
        response = self.client.get(reverse("scan-list"), format="json")
        for obj in response.data["results"]:
            self.assertNotEqual(obj["id"], 3)

    def test_user_should_not_have_access_to_scan_3_in_detail(self):
        response = self.client.get("http://testserver/api/v2/scans/3/")
        self.assertEqual(response.status_code, 404)


class ImportScanTest(BaseClass.RESTEndpointTest):
    fixtures = ["dojo_testdata.json"]

    def __init__(self, *args, **kwargs):
        self.endpoint_model = Test
        self.viewname = "importscan"
        self.viewset = ImportScanView
        self.payload = {
            "scan_date": "2017-12-30",
            "minimum_severity": "Low",
            "active": False,
            "verified": True,
            "scan_type": "ZAP Scan",
            "file": open("tests/zap_sample.xml"),
            "engagement": 1,
            "lead": 2,
            "tags": ["ci/cd", "api"],
            "version": "1.0.0",
        }
        BaseClass.RESTEndpointTest.__init__(self, *args, **kwargs)


class ReimportScanTest(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="admin")
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_import_zap_xml(self):
        length = Test.objects.all().count()
        response = self.client.post(
            reverse("reimportscan-list"),
            {
                "scan_date": "2017-12-30",
                "minimum_severity": "Low",
                "active": True,
                "verified": True,
                "scan_type": "ZAP Scan",
                "file": open("tests/zap_sample.xml"),
                "test": 3,
                "version": "1.0.1",
            },
        )
        self.assertEqual(length, Test.objects.all().count())
        self.assertEqual(201, response.status_code, response.content[:1000])
