from django.test import tag
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework.test import APITestCase, force_authenticate, APIClient
from rest_framework.mixins import (
    RetrieveModelMixin,
    ListModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
)
from rest_framework import status
from drf_yasg2.generators import OpenAPISchemaGenerator
from drf_yasg2.openapi import Info, SchemaRef
from drf_yasg2.openapi import (
    TYPE_ARRAY,
    TYPE_BOOLEAN,
    TYPE_INTEGER,
    TYPE_NUMBER,
    TYPE_OBJECT,
    TYPE_STRING,
)
from collections import OrderedDict

from dojo.api_v2.views import (
    DevelopmentEnvironmentViewSet,
    EndpointStatusViewSet,
    EndPointViewSet,
    EngagementViewSet,
    FindingTemplatesViewSet,
    FindingViewSet,
    JiraInstanceViewSet,
    DojoMetaViewSet,
    NoteTypeViewSet,
    NotesViewSet,
    ProductTypeViewSet,
    ProductViewSet,
    RegulationsViewSet,
    ScanSettingsViewSet,
    ScansViewSet,
    SonarqubeIssueViewSet,
    SonarqubeProductViewSet,
    SonarqubeIssueTransitionViewSet,
    StubFindingsViewSet,
    SystemSettingsViewSet,
    TestTypesViewSet,
    TestsViewSet,
    ToolConfigurationsViewSet,
    ToolProductSettingsViewSet,
    ToolTypesViewSet,
    UsersViewSet,
    JiraIssuesViewSet,
    JiraProjectViewSet,
    AppAnalysisViewSet,
)

from dojo.models import (
    Development_Environment,
    Endpoint_Status,
    Endpoint,
    Engagement,
    Finding_Template,
    Finding,
    JIRA_Instance,
    JIRA_Issue,
    DojoMeta,
    Note_Type,
    Notes,
    Product_Type,
    Product,
    Regulation,
    ScanSettings,
    Scan,
    Sonarqube_Issue,
    Sonarqube_Product,
    Sonarqube_Issue_Transition,
    Stub_Finding,
    System_Settings,
    Test_Type,
    Test,
    Tool_Configuration,
    Tool_Product_Settings,
    Tool_Type,
    Dojo_User,
    JIRA_Project,
    App_Analysis,
)

from dojo.api_v2.serializers import (
    DevelopmentEnvironmentSerializer,
    EndpointStatusSerializer,
    EndpointSerializer,
    EngagementSerializer,
    FindingTemplateSerializer,
    FindingSerializer,
    JIRAInstanceSerializer,
    JIRAIssueSerializer,
    JIRAProjectSerializer,
    MetaSerializer,
    NoteTypeSerializer,
    ProductSerializer,
    RegulationSerializer,
    ScanSettingsSerializer,
    ScanSerializer,
    SonarqubeIssueSerializer,
    SonarqubeProductSerializer,
    SonarqubeIssueTransitionSerializer,
    StubFindingSerializer,
    SystemSettingsSerializer,
    TestTypeSerializer,
    TestSerializer,
    ToolConfigurationSerializer,
    ToolProductSettingsSerializer,
    ToolTypeSerializer,
    UserSerializer,
    NoteSerializer,
    ProductTypeSerializer,
    AppAnalysisSerializer,
)

SWAGGER_SCHEMA_GENERATOR = OpenAPISchemaGenerator(Info("defectdojo", "v2"))
BASE_API_URL = "/api/v2"


def testIsBroken(method):
    return tag("broken")(method)


def skipIfNotSubclass(baseclass):
    def decorate(f):
        def wrapper(self, *args, **kwargs):
            if not issubclass(self.viewset, baseclass):
                self.skipTest("This view is not %s" % baseclass)
            else:
                f(self, *args, **kwargs)

        return wrapper

    return decorate


def check_response_valid(expected_code, response):
    def _data_to_str(response):
        if hasattr(response, "data"):
            return response.data
        return None

    assert (
        response.status_code == expected_code
    ), f"Response invalid, returned with code {response.status_code}\nResponse Data:\n{_data_to_str(response)}"


def format_url(path):
    return f"{BASE_API_URL}{path}"


class SchemaChecker:
    def __init__(self, definitions):
        self._prefix = []
        self._has_failed = False
        self._definitions = definitions
        self._errors = []

    def _register_error(self, error):
        self._errors += [error]

    def _check_or_fail(self, condition, message):
        if not condition:
            self._has_failed = True
            self._register_error(message)

    def _get_prefix(self):
        return "#".join(self._prefix)

    def _push_prefix(self, prefix):
        self._prefix += [prefix]

    def _pop_prefix(self):
        self._prefix = self._prefix if len(self._prefix) == 0 else self._prefix[:-1]

    def _resolve_if_ref(self, schema):
        if type(schema) is not SchemaRef:
            return schema

        ref_name = schema["$ref"]
        ref_name = ref_name[ref_name.rfind("/") + 1 :]
        return self._definitions[ref_name]

    def _check_has_required_fields(self, required_fields, obj):
        for required_field in required_fields:
            field = f"{self._get_prefix()}#{required_field}"
            self._check_or_fail(
                obj is not None and required_field in obj,
                f"{field} is required but was not returned",
            )

    def _check_type(self, schema, obj):
        schema_type = schema["type"]
        is_nullable = schema.get("x-nullable", False) or schema.get("readOnly", False)

        def _check_helper(check):
            self._check_or_fail(
                check,
                f"{self._get_prefix()} should be of type {schema_type} but value was of type {type(obj)}",
            )

        if obj is None:
            self._check_or_fail(
                is_nullable,
                f"{self._get_prefix()} is not nullable yet the value returned was null",
            )
        elif schema_type is TYPE_BOOLEAN:
            _check_helper(isinstance(obj, bool))
        elif schema_type is TYPE_INTEGER:
            _check_helper(isinstance(obj, int))
        elif schema_type is TYPE_NUMBER:
            _check_helper(obj.isdecimal())
        elif schema_type is TYPE_ARRAY:
            _check_helper(isinstance(obj, list))
        elif schema_type is TYPE_OBJECT:
            _check_helper(isinstance(obj, OrderedDict) or isinstance(obj, dict))
        elif schema_type is TYPE_STRING:
            _check_helper(isinstance(obj, str))
        else:
            # Default case
            _check_helper(False)

    def _with_prefix(self, prefix, callable, *args):
        self._push_prefix(prefix)
        callable(*args)
        self._pop_prefix()

    def check(self, schema, obj):
        def _check(schema, obj):
            schema = self._resolve_if_ref(schema)
            self._check_type(schema, obj)

            required_fields = schema.get("required", [])
            self._check_has_required_fields(required_fields, obj)

            if obj is None:
                return

            properties = schema.get("properties", None)
            if properties is not None:
                for name, prop in properties.items():
                    obj_child = obj.get(name, None)
                    if obj_child is not None:
                        self._with_prefix(name, _check, prop, obj_child)

            additional_properties = schema.get("additionalProperties", None)
            if additional_properties is not None:
                for name, obj_child in obj.items():
                    self._with_prefix(
                        f"additionalProp<{name}>",
                        _check,
                        additional_properties,
                        obj_child,
                    )

            if schema["type"] is TYPE_ARRAY:
                items_schema = schema["items"]
                for index in range(len(obj)):
                    self._with_prefix(f"item{index}", _check, items_schema, obj[index])

        self._has_failed = False
        self._errors = []
        self._prefix = []
        _check(schema, obj)
        assert not self._has_failed, (
            "\n"
            + "\n".join(self._errors)
            + "\nFailed with "
            + str(len(self._errors))
            + " errors"
        )


class BaseClass:
    class SchemaTest(APITestCase):
        fixtures = ["dojo_testdata.json"]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.viewset = None
            self.viewname = None
            self.model = None
            self.serializer = None
            self.field_transformers = dict()

        def setUp(self):
            super().setUp()
            testuser = Dojo_User.objects.get(username="admin")

            factory = APIRequestFactory()
            request = factory.get("/")
            force_authenticate(request, user=testuser)
            request = APIView().initialize_request(request)

            self.schema = SWAGGER_SCHEMA_GENERATOR.get_schema(request, public=True)
            self.client = APIClient()
            self.client.force_authenticate(user=testuser)

        def check_schema(self, schema, obj):
            schema_checker = SchemaChecker(self.schema["definitions"])
            schema_checker.check(schema, obj)

        def get_valid_object_id(self):
            response = self.client.get(format_url(f"/{self.viewname}/"))
            check_response_valid(status.HTTP_200_OK, response)
            if len(response.data["results"]) == 0:
                return None

            return response.data["results"][0].get("id", None)

        def get_endpoint_schema(self, path, method):
            paths = self.schema["paths"]
            methods = paths.get(path, None)
            assert (
                methods is not None
            ), f"{path} not found in {[path for path in paths.keys()]}"

            endpoint = methods.get(method, None)
            assert (
                endpoint is not None
            ), f"Method {method} not found in {[method for method in methods.keys()]}"

            return endpoint

        def construct_response_data(self, obj_id):
            obj = self.model.objects.get(id=obj_id)
            request = APIView().initialize_request(APIRequestFactory().request())
            serialized_obj = self.serializer(
                context={"request": request}
            ).to_representation(obj)

            for name, transformer in self.field_transformers.items():
                serialized_obj[name] = transformer(serialized_obj[name])

            return serialized_obj

        @skipIfNotSubclass(ListModelMixin)
        def test_list_endpoint(self, extra_args=None):
            endpoints = self.schema["paths"][f"/{self.viewname}/"]
            response = self.client.get(format_url(f"/{self.viewname}/"), extra_args)
            check_response_valid(status.HTTP_200_OK, response)

            schema = endpoints["get"]["responses"]["200"]["schema"]
            obj = response.data

            self.check_schema(schema, obj)

        @skipIfNotSubclass(RetrieveModelMixin)
        def test_retrieve_endpoint(self, extra_args=None):
            endpoints = self.schema["paths"][f"/{self.viewname}/{{id}}/"]
            response = self.client.get(format_url(f"/{self.viewname}/"))
            check_response_valid(status.HTTP_200_OK, response)
            ids = [obj["id"] for obj in response.data["results"]]

            schema = endpoints["get"]["responses"]["200"]["schema"]
            for id in ids:
                response = self.client.get(
                    format_url(f"/{self.viewname}/{id}/"), extra_args
                )
                check_response_valid(status.HTTP_200_OK, response)
                obj = response.data
                self.check_schema(schema, obj)

        @skipIfNotSubclass(UpdateModelMixin)
        def test_patch_endpoint(self, extra_args=None):
            operation = self.schema["paths"][f"/{self.viewname}/{{id}}/"]["patch"]

            id = self.get_valid_object_id()
            if id is None:
                self.skipTest("No data exists to test endpoint")

            data = self.construct_response_data(id)

            schema = operation["responses"]["200"]["schema"]
            response = self.client.patch(
                format_url(f"/{self.viewname}/{id}/"), data, format="json"
            )
            check_response_valid(status.HTTP_200_OK, response)

            obj = response.data
            self.check_schema(schema, obj)

        @skipIfNotSubclass(UpdateModelMixin)
        def test_put_endpoint(self, extra_args=None):
            operation = self.schema["paths"][f"/{self.viewname}/{{id}}/"]["put"]

            id = self.get_valid_object_id()
            if id is None:
                self.skipTest("No data exists to test endpoint")

            data = self.construct_response_data(id)

            schema = operation["responses"]["200"]["schema"]
            response = self.client.put(
                format_url(f"/{self.viewname}/{id}/"), data, format="json"
            )
            check_response_valid(status.HTTP_200_OK, response)

            obj = response.data
            self.check_schema(schema, obj)

        @skipIfNotSubclass(CreateModelMixin)
        def test_post_endpoint(self, extra_args=None):
            operation = self.schema["paths"][f"/{self.viewname}/"]["post"]

            id = self.get_valid_object_id()
            if id is None:
                self.skipTest("No data exists to test endpoint")

            data = self.construct_response_data(id)

            schema = operation["responses"]["201"]["schema"]
            response = self.client.post(
                format_url(f"/{self.viewname}/"), data, format="json"
            )
            check_response_valid(status.HTTP_201_CREATED, response)

            obj = response.data
            self.check_schema(schema, obj)


class DevelopmentEnvironmentTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "development_environments"
        self.viewset = DevelopmentEnvironmentViewSet
        self.model = Development_Environment
        self.serializer = DevelopmentEnvironmentSerializer


class EndpointStatusTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "endpoint_status"
        self.viewset = EndpointStatusViewSet
        self.model = Endpoint_Status
        self.serializer = EndpointStatusSerializer


class EndpointTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "endpoints"
        self.viewset = EndPointViewSet
        self.model = Endpoint
        self.serializer = EndpointSerializer
        self.field_transformers = {"path": lambda v: v + "transformed/"}


class EngagementTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "engagements"
        self.viewset = EngagementViewSet
        self.model = Engagement
        self.serializer = EngagementSerializer

    @testIsBroken
    def test_accept_risks(self):
        operation = self.get_endpoint_schema("/engagements/{id}/accept_risks/", "post")
        schema = operation["responses"]["201"]["schema"]
        id = self.get_valid_object_id()
        if id is None:
            self.skipTest("No data exists to test endpoint")

        data = [{"cve": 1, "justification": "test", "accepted_by": "2"}]

        response = self.client.post(
            format_url(f"/engagements/{id}/accept_risks/"), data, format="json"
        )
        check_response_valid(201, response)
        obj = response.data
        self.check_schema(schema, obj)

    @testIsBroken
    def test_notes_read(self):
        operation = self.get_endpoint_schema("/engagements/{id}/notes/", "get")
        schema = operation["responses"]["200"]["schema"]
        id = self.get_valid_object_id()
        if id is None:
            self.skipTest("No data exists to test endpoint")

        response = self.client.get(format_url(f"/engagements/{id}/notes/"))
        check_response_valid(200, response)
        obj = response.data
        self.check_schema(schema, obj)

    @testIsBroken
    def test_notes_create(self):
        operation = self.get_endpoint_schema("/engagements/{id}/notes/", "post")
        schema = operation["responses"]["201"]["schema"]
        id = self.get_valid_object_id()
        if id is None:
            self.skipTest("No data exists to test endpoint")

        data = {
            "entry": "test",
            "author": 2,
        }

        response = self.client.post(
            format_url(f"/engagements/{id}/notes/"), data, format="json"
        )
        check_response_valid(201, response)
        obj = response.data
        self.check_schema(schema, obj)


class FindingTemplateTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "finding_templates"
        self.viewset = FindingTemplatesViewSet
        self.model = Finding_Template
        self.serializer = FindingTemplateSerializer

    @testIsBroken
    def test_post_endpoint(self):
        super().test_post_endpoint()

    @testIsBroken
    def test_patch_endpoint(self):
        super().test_patch_endpoint()

    @testIsBroken
    def test_put_endpoint(self):
        super().test_put_endpoint()


class FindingTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "findings"
        self.viewset = FindingViewSet
        self.model = Finding
        self.serializer = FindingSerializer

    @testIsBroken
    def test_list_endpoint(self):
        super().test_list_endpoint({"related_fields": True})

    @testIsBroken
    def test_patch_endpoint(self):
        super().test_patch_endpoint()

    @testIsBroken
    def test_put_endpoint(self):
        super().test_put_endpoint()

    @testIsBroken
    def test_retrieve_endpoint(self):
        super().test_retrieve_endpoint({"related_fields": True})


class JiraInstanceTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "jira_instances"
        self.viewset = JiraInstanceViewSet
        self.model = JIRA_Instance
        self.serializer = JIRAInstanceSerializer

    @testIsBroken
    def test_list_endpoint(self):
        super().test_list_endpoint()

    @testIsBroken
    def test_patch_endpoint(self):
        super().test_patch_endpoint()

    @testIsBroken
    def test_put_endpoint(self):
        super().test_put_endpoint()

    @testIsBroken
    def test_retrieve_endpoint(self):
        super().test_retrieve_endpoint()

    @testIsBroken
    def test_post_endpoint(self):
        super().test_post_endpoint()


class JiraFindingMappingsTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "jira_finding_mappings"
        self.viewset = JiraIssuesViewSet
        self.model = JIRA_Issue
        self.serializer = JIRAIssueSerializer
        self.field_transformers = {"finding": lambda v: 2, "engagement": lambda v: 2}


class JiraProjectTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "jira_projects"
        self.viewset = JiraProjectViewSet
        self.model = JIRA_Project
        self.serializer = JIRAProjectSerializer


class MetadataTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "metadata"
        self.viewset = DojoMetaViewSet
        self.model = DojoMeta
        self.serializer = MetaSerializer


class NoteTypeTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "note_type"
        self.viewset = NoteTypeViewSet
        self.model = Note_Type
        self.serializer = NoteTypeSerializer
        self.field_transformers = {"name": lambda v: v + "_new"}


class NoteTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "notes"
        self.viewset = NotesViewSet
        self.model = Notes
        self.serializer = NoteSerializer


class ProductTypeTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "product_types"
        self.viewset = ProductTypeViewSet
        self.model = Product_Type
        self.serializer = ProductTypeSerializer
        self.field_transformers = {"name": lambda v: v + "_new"}


class ProductTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "products"
        self.viewset = ProductViewSet
        self.model = Product
        self.serializer = ProductSerializer
        self.field_transformers = {"name": lambda v: v + "_new"}

    @testIsBroken
    def test_list_endpoint(self):
        super().test_list_endpoint()

    @testIsBroken
    def test_patch_endpoint(self):
        super().test_patch_endpoint()

    @testIsBroken
    def test_put_endpoint(self):
        super().test_put_endpoint()

    @testIsBroken
    def test_retrieve_endpoint(self):
        super().test_retrieve_endpoint()

    @testIsBroken
    def test_post_endpoint(self):
        super().test_post_endpoint()


class RegulationTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "regulations"
        self.viewset = RegulationsViewSet
        self.model = Regulation
        self.serializer = RegulationSerializer


class ScanSettingsTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "scan_settings"
        self.viewset = ScanSettingsViewSet
        self.model = ScanSettings
        self.serializer = ScanSettingsSerializer


class ScanTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "scans"
        self.viewset = ScansViewSet
        self.model = Scan
        self.serializer = ScanSerializer


class SonarqubeIssuesTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "sonarqube_issues"
        self.viewset = SonarqubeIssueViewSet
        self.model = Sonarqube_Issue
        self.serializer = SonarqubeIssueSerializer
        self.field_transformers = {"key": lambda v: v + "_new"}


class SonarqubeProductConfTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "sonarqube_product_configurations"
        self.viewset = SonarqubeProductViewSet
        self.model = Sonarqube_Product
        self.serializer = SonarqubeProductSerializer


class SonarqubeTransitionTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "sonarqube_transitions"
        self.viewset = SonarqubeIssueTransitionViewSet
        self.model = Sonarqube_Issue_Transition
        self.serializer = SonarqubeIssueTransitionSerializer


class StubFindingTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "stub_findings"
        self.viewset = StubFindingsViewSet
        self.model = Stub_Finding
        self.serializer = StubFindingSerializer


class SystemSettingTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "system_settings"
        self.viewset = SystemSettingsViewSet
        self.model = System_Settings
        self.serializer = SystemSettingsSerializer


class AppAnalysisTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "technologies"
        self.viewset = AppAnalysisViewSet
        self.model = App_Analysis
        self.serializer = AppAnalysisSerializer

    @testIsBroken
    def test_patch_endpoint(self):
        super().test_patch_endpoint()

    @testIsBroken
    def test_put_endpoint(self):
        super().test_put_endpoint()

    @testIsBroken
    def test_post_endpoint(self):
        super().test_post_endpoint()


class TestTypeTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "test_types"
        self.viewset = TestTypesViewSet
        self.model = Test_Type
        self.serializer = TestTypeSerializer
        self.field_transformers = {"name": lambda v: v + "_new"}


class TestsTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "tests"
        self.viewset = TestsViewSet
        self.model = Test
        self.serializer = TestSerializer


class ToolConfigurationTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "tool_configurations"
        self.viewset = ToolConfigurationsViewSet
        self.model = Tool_Configuration
        self.serializer = ToolConfigurationSerializer


class ToolProductSettingTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "tool_product_settings"
        self.viewset = ToolProductSettingsViewSet
        self.model = Tool_Product_Settings
        self.serializer = ToolProductSettingsSerializer


class ToolTypeTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "tool_types"
        self.viewset = ToolTypesViewSet
        self.model = Tool_Type
        self.serializer = ToolTypeSerializer


class UserTest(BaseClass.SchemaTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewname = "users"
        self.viewset = UsersViewSet
        self.model = Dojo_User
        self.serializer = UserSerializer
        self.field_transformers = {"username": lambda v: v + "_transformed"}
