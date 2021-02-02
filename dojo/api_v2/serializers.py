from drf_yasg2.utils import swagger_serializer_method
from dojo.models import (
    Product,
    Engagement,
    Test,
    Finding,
    User,
    ScanSettings,
    IPScan,
    Scan,
    Stub_Finding,
    Risk_Acceptance,
    Finding_Template,
    Test_Type,
    Development_Environment,
    NoteHistory,
    JIRA_Issue,
    Tool_Product_Settings,
    Tool_Configuration,
    Tool_Type,
    Product_Type,
    JIRA_Instance,
    Endpoint,
    BurpRawRequestResponse,
    JIRA_Project,
    Notes,
    DojoMeta,
    FindingImage,
    Note_Type,
    App_Analysis,
    Endpoint_Status,
    Sonarqube_Issue,
    Sonarqube_Issue_Transition,
    Sonarqube_Product,
    Regulation,
    System_Settings,
    FileUpload,
)

from dojo.forms import ImportScanForm, SEVERITY_CHOICES
from dojo.tools.factory import import_parser_factory, requires_file
from dojo.utils import max_safe, is_scan_file_too_large
from dojo.notifications.helper import create_notification
from django.urls import reverse

from django.core.validators import URLValidator, validate_ipv46_address
from django.conf import settings
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils import timezone
import base64
import datetime
import six
from django.utils.translation import ugettext_lazy as _
import json
import dojo.jira_link.helper as jira_helper
import logging
import tagulous
import dojo.finding.helper as finding_helper


logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


class TagList(list):
    def __init__(self, *args, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)
        list.__init__(self, *args, **kwargs)
        self.pretty_print = pretty_print

    def __add__(self, rhs):
        return TagList(list.__add__(self, rhs))

    def __getitem__(self, item):
        result = list.__getitem__(self, item)
        try:
            return TagList(result)
        except TypeError:
            return result

    def __str__(self):
        if self.pretty_print:
            return json.dumps(self, sort_keys=True, indent=4, separators=(",", ": "))
        else:
            return json.dumps(self)


class TagListSerializerField(serializers.ListField):
    child = serializers.CharField()
    default_error_messages = {
        "not_a_list": _('Expected a list of items but got type "{input_type}".'),
        "invalid_json": _(
            "Invalid json list. A tag list submitted in string"
            " form must be valid json."
        ),
        "not_a_str": _("All list items must be of string type."),
    }
    order_by = None

    def __init__(self, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)

        style = kwargs.pop("style", {})
        kwargs["style"] = {"base_template": "textarea.html"}
        kwargs["style"].update(style)

        super(TagListSerializerField, self).__init__(**kwargs)

        self.pretty_print = pretty_print

    def to_internal_value(self, data):
        if isinstance(data, six.string_types):
            if not data:
                data = []
            try:
                data = json.loads(data)
            except ValueError:
                self.fail("invalid_json")

        logger.debug("data as json: %s", data)

        if not isinstance(data, list):
            self.fail("not_a_list", input_type=type(data).__name__)

        # data_safe = []
        for s in data:
            if not isinstance(s, six.string_types):
                self.fail("not_a_str")

            self.child.run_validation(s)

            # if ' ' in s or ',' in s:
            #     s = '"%s"' % s

            # data_safe.append(s)

        # internal_value = ','.join(data_safe)

        internal_value = tagulous.utils.render_tags(data)

        return internal_value
        # return data

    def to_representation(self, value):
        if not isinstance(value, TagList):

            # we can't use isinstance because TagRelatedManager is non-existing class
            # it cannot be imported or referenced, so we fallback to string comparison
            if type(value).__name__ == "TagRelatedManager":
                # if self.order_by:
                #     tags = value.all().order_by(*self.order_by)
                # else:
                #     tags = value.all()
                # value = [tag.name for tag in tags]

                value = value.get_tag_list()

            elif isinstance(value, str):
                value = tagulous.utils.parse_tags(value)

            # elif len(value) > 0 and isinstance(value[0], Tag):
            #     raise ValueError('unreachable code?!')
            #     print('to_representation4: ' + str(value))
            #     # .. but sometimes the queryset already has been converted into a list, i.e. by prefetch_related
            #     tags = value
            #     value = [tag.name for tag in tags]
            #     if self.order_by:
            #         # the only possible ordering is by name, so we order after creating the list
            #         value = sorted(value)
            else:
                raise ValueError(
                    "unable to convert %s into TagList" % type(value).__name__
                )

            value = TagList(value, pretty_print=self.pretty_print)
        return value


class TaggitSerializer(serializers.Serializer):
    def create(self, validated_data):
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        tag_object = super(TaggitSerializer, self).create(validated_data)

        return self._save_tags(tag_object, to_be_tagged)

    def update(self, instance, validated_data):
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        tag_object = super(TaggitSerializer, self).update(instance, validated_data)

        return self._save_tags(tag_object, to_be_tagged)

    def _save_tags(self, tag_object, tags):
        for key in list(tags.keys()):
            tag_values = tags.get(key)
            # tag_object.tags = ", ".join(tag_values)
            tag_object.tags = tag_values
        tag_object.save()

        return tag_object

    def _pop_tags(self, validated_data):
        to_be_tagged = {}

        for key in list(self.fields.keys()):
            field = self.fields[key]
            if isinstance(field, TagListSerializerField):
                if key in validated_data:
                    to_be_tagged[key] = validated_data.pop(key)

        return (to_be_tagged, validated_data)


class RequestResponseDict(list):
    def __init__(self, *args, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)
        list.__init__(self, *args, **kwargs)
        self.pretty_print = pretty_print

    def __add__(self, rhs):
        return RequestResponseDict(list.__add__(self, rhs))

    def __getitem__(self, item):
        result = list.__getitem__(self, item)
        try:
            return RequestResponseDict(result)
        except TypeError:
            return result

    def __str__(self):
        if self.pretty_print:
            return json.dumps(self, sort_keys=True, indent=4, separators=(",", ": "))
        else:
            return json.dumps(self)


class RequestResponseSerializerField(serializers.ListSerializer):
    child = serializers.CharField()
    default_error_messages = {
        "not_a_list": _('Expected a list of items but got type "{input_type}".'),
        "invalid_json": _(
            "Invalid json list. A tag list submitted in string"
            " form must be valid json."
        ),
        "not_a_dict": _(
            "All list items must be of dict type with keys 'request' and 'response'"
        ),
        "not_a_str": _("All values in the dict must be of string type."),
    }
    order_by = None

    def __init__(self, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)

        style = kwargs.pop("style", {})
        kwargs["style"] = {"base_template": "textarea.html"}
        kwargs["style"].update(style)

        if "data" in kwargs:
            data = kwargs["data"]

            if isinstance(data, list):
                kwargs["many"] = True

        super(RequestResponseSerializerField, self).__init__(**kwargs)

        self.pretty_print = pretty_print

    def to_internal_value(self, data):
        if isinstance(data, six.string_types):
            if not data:
                data = []
            try:
                data = json.loads(data)
            except ValueError:
                self.fail("invalid_json")

        if not isinstance(data, list):
            self.fail("not_a_list", input_type=type(data).__name__)
        for s in data:
            if not isinstance(s, dict):
                self.fail("not_a_dict", input_type=type(s).__name__)

            request = s.get("request", None)
            response = s.get("response", None)

            if not isinstance(request, str):
                self.fail("not_a_str", input_type=type(request).__name__)
            if not isinstance(response, str):
                self.fail("not_a_str", input_type=type(request).__name__)

            self.child.run_validation(request)
            self.child.run_validation(response)
        return data

    def to_representation(self, value):
        if not isinstance(value, RequestResponseDict):
            if not isinstance(value, list):
                # this will trigger when a queryset is found...
                if self.order_by:
                    burps = value.all().order_by(*self.order_by)
                else:
                    burps = value.all()
                value = [
                    {"request": burp.get_request(), "response": burp.get_response()}
                    for burp in burps
                ]
        return value


class MetaSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, default=None, allow_null=True
    )
    endpoint = serializers.PrimaryKeyRelatedField(
        queryset=Endpoint.objects.all(), required=False, default=None, allow_null=True
    )
    finding = serializers.PrimaryKeyRelatedField(
        queryset=Finding.objects.all(), required=False, default=None, allow_null=True
    )

    def validate(self, data):
        DojoMeta(**data).clean()
        return data

    class Meta:
        model = DojoMeta
        fields = "__all__"


class ProductMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DojoMeta
        fields = ("name", "value")


class UserSerializer(serializers.ModelSerializer):
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "last_login",
            "is_active",
            "is_staff",
            "is_superuser",
        )


class NoteHistorySerializer(serializers.ModelSerializer):
    current_editor = UserSerializer(read_only=True)

    class Meta:
        model = NoteHistory
        fields = "__all__"


class NoteSerializer(serializers.ModelSerializer):
    author = UserSerializer(many=False, read_only=True)
    editor = UserSerializer(read_only=True, many=False, allow_null=True)

    history = NoteHistorySerializer(read_only=True, many=True)

    def update(self, instance, validated_data):
        instance.entry = validated_data["entry"]
        instance.edited = True
        instance.editor = self.context["request"].user
        instance.edit_time = timezone.now()
        history = NoteHistory(
            data=instance.entry, time=instance.edit_time, current_editor=instance.editor
        )
        history.save()
        instance.history.add(history)
        instance.save()
        return instance

    class Meta:
        model = Notes
        fields = "__all__"


class NoteTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note_Type
        fields = "__all__"


class FileSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=True)

    class Meta:
        model = FileUpload
        fields = "__all__"


class ProductSerializer(TaggitSerializer, serializers.ModelSerializer):
    findings_count = serializers.SerializerMethodField()
    findings_list = serializers.SerializerMethodField()

    tags = TagListSerializerField(required=False)
    product_meta = ProductMetaSerializer(read_only=True, many=True)

    class Meta:
        model = Product
        exclude = ("tid", "manager", "prod_manager", "tech_contact", "updated")
        extra_kwargs = {
            "authorized_users": {
                "queryset": User.objects.exclude(is_staff=True).exclude(is_active=False)
            }
        }

    def get_findings_count(self, obj):
        return obj.findings_count

    def get_findings_list(self, obj):
        return obj.open_findings_list()


class ProductTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product_Type
        fields = "__all__"
        extra_kwargs = {
            "authorized_users": {
                "queryset": User.objects.exclude(is_staff=True).exclude(is_active=False)
            }
        }


class EngagementSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Engagement
        fields = "__all__"

    def validate(self, data):
        if self.context["request"].method == "POST":
            if data["target_start"] > data["target_end"]:
                raise serializers.ValidationError(
                    "Your target start date exceeds your target end date"
                )
        return data

    def build_relational_field(self, field_name, relation_info):
        if field_name == "notes":
            return NoteSerializer, {"many": True, "read_only": True}
        if field_name == "files":
            return FileSerializer, {"many": True, "read_only": True}
        return super().build_relational_field(field_name, relation_info)


class EngagementToNotesSerializer(serializers.Serializer):
    engagement_id = serializers.PrimaryKeyRelatedField(
        queryset=Engagement.objects.all(), many=False, allow_null=True
    )
    notes = NoteSerializer(many=True)


class EngagementToFilesSerializer(serializers.Serializer):
    engagement_id = serializers.PrimaryKeyRelatedField(
        queryset=Engagement.objects.all(), many=False, allow_null=True
    )
    files = FileSerializer(many=True)


class AppAnalysisSerializer(serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = App_Analysis
        fields = "__all__"


class ToolTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool_Type
        fields = "__all__"


class RegulationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Regulation
        fields = "__all__"


class ToolConfigurationSerializer(serializers.ModelSerializer):
    configuration_url = serializers.CharField(source="url")

    class Meta:
        model = Tool_Configuration
        fields = "__all__"
        extra_kwargs = {
            "password": {"write_only": True},
            "ssh": {"write_only": True},
            "api_key": {"write_only": True},
        }


class ToolProductSettingsSerializer(serializers.ModelSerializer):
    setting_url = serializers.CharField(source="url")

    class Meta:
        model = Tool_Product_Settings
        fields = "__all__"


class EndpointStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endpoint_Status
        fields = "__all__"

    def create(self, validated_data):
        endpoint = validated_data["endpoint"]
        finding = validated_data["finding"]
        status = Endpoint_Status.objects.create(finding=finding, endpoint=endpoint)
        endpoint.endpoint_status.add(status)
        finding.endpoint_status.add(status)
        status.mitigated = validated_data.get("mitigated", False)
        status.false_positive = validated_data.get("false_positive", False)
        status.out_of_scope = validated_data.get("out_of_scope", False)
        status.risk_accepted = validated_data.get("risk_accepted", False)
        status.date = validated_data.get("date", timezone.now())
        status.save()
        return status


class EndpointSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Endpoint
        fields = "__all__"

    def validate(self, data):
        # print('EndpointSerialize.validate')
        port_re = (
            "(:[0-9]{1,5}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}"
            "|655[0-2][0-9]|6553[0-5])"
        )

        if not self.context["request"].method == "PATCH":
            if (
                "host" not in data
                or "protocol" not in data
                or "path" not in data
                or "query" not in data
                or "fragment" not in data
            ):
                raise serializers.ValidationError(
                    "Please provide valid host, protocol, path, query and " "fragment"
                )
            protocol = data["protocol"]
            path = data["path"]
            query = data["query"]
            fragment = data["fragment"]
            host = data["host"]
        else:
            protocol = data.get("protocol", self.instance.protocol)
            path = data.get("path", self.instance.path)
            query = data.get("query", self.instance.query)
            fragment = data.get("fragment", self.instance.fragment)
            host = data.get("host", self.instance.host)
        product = data.get("product", None)

        from urllib.parse import urlunsplit

        if protocol:
            endpoint = urlunsplit((protocol, host, path, query, fragment))
        else:
            endpoint = host

        from django.core import exceptions
        from django.core.validators import RegexValidator
        import re

        try:
            url_validator = URLValidator()
            url_validator(endpoint)
        except exceptions.ValidationError:
            try:
                # do we have a port number?
                regex = re.compile(port_re)
                host = endpoint
                if regex.findall(endpoint):
                    for g in regex.findall(endpoint):
                        host = re.sub(port_re, "", host)
                validate_ipv46_address(host)
            except exceptions.ValidationError:
                try:
                    validate_hostname = RegexValidator(
                        regex=r"[a-zA-Z0-9-_]*\.[a-zA-Z]{2,6}"
                    )
                    # do we have a port number?
                    regex = re.compile(port_re)
                    host = endpoint
                    if regex.findall(endpoint):
                        for g in regex.findall(endpoint):
                            host = re.sub(port_re, "", host)
                    validate_hostname(host)
                except:  # noqa
                    raise serializers.ValidationError(
                        "It does not appear as though this endpoint is a "
                        "valid URL or IP address.",
                        code="invalid",
                    )

        endpoint = Endpoint.objects.filter(
            protocol=protocol,
            host=host,
            path=path,
            query=query,
            fragment=fragment,
            product=product,
        )
        if endpoint.count() > 0 and not self.instance:
            raise serializers.ValidationError(
                "It appears as though an endpoint with this data already "
                "exists for this product.",
                code="invalid",
            )

        return data


class JIRAIssueSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JIRA_Issue
        fields = "__all__"

    def get_url(self, obj):
        return jira_helper.get_jira_issue_url(obj)


class JIRAInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = JIRA_Instance
        fields = "__all__"
        extra_kwargs = {
            "password": {"write_only": True},
        }


class JIRAProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = JIRA_Project
        fields = "__all__"


class SonarqubeIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sonarqube_Issue
        fields = "__all__"


class SonarqubeIssueTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sonarqube_Issue_Transition
        fields = "__all__"


class SonarqubeProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sonarqube_Product
        fields = "__all__"


class DevelopmentEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Development_Environment
        fields = "__all__"


class TestSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)
    test_type_name = serializers.ReadOnlyField()

    class Meta:
        model = Test
        fields = "__all__"

    def build_relational_field(self, field_name, relation_info):
        if field_name == "notes":
            return NoteSerializer, {"many": True, "read_only": True}
        if field_name == "files":
            return FileSerializer, {"many": True, "read_only": True}
        return super().build_relational_field(field_name, relation_info)


class TestCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    engagement = serializers.PrimaryKeyRelatedField(queryset=Engagement.objects.all())
    notes = serializers.PrimaryKeyRelatedField(
        allow_null=True, default=[], queryset=Notes.objects.all(), many=True
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Test
        fields = "__all__"


class TestTypeSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Test_Type
        fields = "__all__"


class TestToNotesSerializer(serializers.Serializer):
    test_id = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all(), many=False, allow_null=True
    )
    notes = NoteSerializer(many=True)


class TestToFilesSerializer(serializers.Serializer):
    test_id = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all(), many=False, allow_null=True
    )
    files = FileSerializer(many=True)


class RiskAcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Risk_Acceptance
        fields = "__all__"


class FindingImageSerializer(serializers.ModelSerializer):
    base64 = serializers.SerializerMethodField()

    class Meta:
        model = FindingImage
        fields = ["base64", "caption", "id"]

    def get_base64(self, obj):
        return base64.b64encode(obj.image.read())


class FindingMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DojoMeta
        fields = ("name", "value")


class FindingProdTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product_Type
        fields = ["id", "name"]


class FindingProductSerializer(serializers.ModelSerializer):
    prod_type = FindingProdTypeSerializer(required=False)

    class Meta:
        model = Product
        fields = ["id", "name", "prod_type"]


class FindingEngagementSerializer(serializers.ModelSerializer):
    product = FindingProductSerializer(required=False)

    class Meta:
        model = Engagement
        fields = ["id", "name", "product", "branch_tag"]


class FindingEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Development_Environment
        fields = ["id", "name"]


class FindingTestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test_Type
        fields = ["id", "name"]


class FindingTestSerializer(serializers.ModelSerializer):
    engagement = FindingEngagementSerializer(required=False)
    environment = FindingEnvironmentSerializer(required=False)
    test_type = FindingTestTypeSerializer(required=False)

    class Meta:
        model = Test
        fields = ["id", "title", "test_type", "engagement", "environment"]


class FindingRelatedFieldsSerializer(serializers.Serializer):
    test = serializers.SerializerMethodField()
    jira = serializers.SerializerMethodField()

    @swagger_serializer_method(FindingTestSerializer)
    def get_test(self, obj):
        return FindingTestSerializer(read_only=True).to_representation(obj.test)

    @swagger_serializer_method(JIRAIssueSerializer)
    def get_jira(self, obj):
        issue = jira_helper.get_jira_issue(obj)
        if issue is None:
            return None
        return JIRAIssueSerializer(read_only=True).to_representation(issue)


class FindingSerializer(TaggitSerializer, serializers.ModelSerializer):
    images = FindingImageSerializer(many=True, read_only=True)
    tags = TagListSerializerField(required=False)
    request_response = serializers.SerializerMethodField()
    accepted_risks = RiskAcceptanceSerializer(
        many=True, read_only=True, source="risk_acceptance_set"
    )
    push_to_jira = serializers.BooleanField(default=False)
    age = serializers.IntegerField(read_only=True)
    sla_days_remaining = serializers.IntegerField(read_only=True)
    finding_meta = FindingMetaSerializer(read_only=True, many=True)
    related_fields = serializers.SerializerMethodField()
    # for backwards compatibility
    jira_creation = serializers.SerializerMethodField(read_only=True)
    jira_change = serializers.SerializerMethodField(read_only=True)
    display_status = serializers.SerializerMethodField()

    class Meta:
        model = Finding
        fields = "__all__"

    @swagger_serializer_method(serializers.DateTimeField())
    def get_jira_creation(self, obj):
        return jira_helper.get_jira_creation(obj)

    @swagger_serializer_method(serializers.DateTimeField())
    def get_jira_change(self, obj):
        return jira_helper.get_jira_change(obj)

    @swagger_serializer_method(FindingRelatedFieldsSerializer)
    def get_related_fields(self, obj):
        request = self.context.get("request", None)
        if request is None:
            return None

        query_params = request.query_params
        if query_params.get("related_fields", "false") == "true":
            return FindingRelatedFieldsSerializer(required=False).to_representation(obj)
        else:
            return None

    @swagger_serializer_method(serializers.ListField(serializers.CharField()))
    def get_display_status(self, obj):
        return obj.status()

    # Overriding this to push add Push to JIRA functionality
    def update(self, instance, validated_data):
        # remove tags from validated data and store them seperately
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        # pop push_to_jira so it won't get send to the model as a field
        # TODO: JIRA can we remove this is_push_all_issues, already checked in apiv2 viewset?
        push_to_jira = validated_data.pop(
            "push_to_jira"
        ) or jira_helper.is_push_all_issues(instance)

        instance = super(TaggitSerializer, self).update(instance, validated_data)

        mitigation_change = finding_helper.update_finding_status(
            instance, self.context["request"].user
        )

        # If we need to push to JIRA, an extra save call is needed.
        # Also if we need to update the mitigation date of the finding.
        # TODO try to combine create and save, but for now I'm just fixing a bug and don't want to change to much
        if push_to_jira or mitigation_change:
            instance.save(push_to_jira=push_to_jira)

        # not sure why we are returning a tag_object, but don't want to change too much now as we're just fixing a bug
        tag_object = self._save_tags(instance, to_be_tagged)
        return tag_object

    def validate(self, data):
        if self.context["request"].method == "PATCH":
            is_active = data.get("active", self.instance.active)
            is_verified = data.get("verified", self.instance.verified)
            is_duplicate = data.get("duplicate", self.instance.duplicate)
            is_false_p = data.get("false_p", self.instance.false_p)
            is_risk_accepted = data.get("risk_accepted", self.instance.risk_accepted)
        else:
            is_active = data.get("active", True)
            is_verified = data.get("verified", True)
            is_duplicate = data.get("duplicate", False)
            is_false_p = data.get("false_p", False)
            is_risk_accepted = data.get("risk_accepted", False)

        if (is_active or is_verified) and is_duplicate:
            raise serializers.ValidationError(
                "Duplicate findings cannot be" " verified or active"
            )
        if is_false_p and is_verified:
            raise serializers.ValidationError(
                "False positive findings cannot " "be verified."
            )

        if is_risk_accepted and not self.instance.risk_accepted:
            if not self.instance.test.engagement.product.enable_simple_risk_acceptance:
                raise serializers.ValidationError(
                    "Simple risk acceptance is disabled for this product, use the UI to accept this finding."
                )

        if is_active and is_risk_accepted:
            raise serializers.ValidationError(
                "Active findings cannot " "be risk accepted."
            )

        return data

    def build_relational_field(self, field_name, relation_info):
        if field_name == "notes":
            return NoteSerializer, {"many": True, "read_only": True}
        return super().build_relational_field(field_name, relation_info)

    def get_request_response(self, obj):
        burp_req_resp = BurpRawRequestResponse.objects.filter(finding=obj)
        burp_list = []
        for burp in burp_req_resp:
            request = burp.get_request()
            response = burp.get_response()
            burp_list.append({"request": request, "response": response})
        serialized_burps = BurpRawRequestResponseSerializer({"req_resp": burp_list})
        return serialized_burps.data


class FindingCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    notes = serializers.PrimaryKeyRelatedField(
        read_only=True, allow_null=True, default=[], many=True
    )
    test = serializers.PrimaryKeyRelatedField(queryset=Test.objects.all())
    thread_id = serializers.IntegerField(default=0)
    found_by = serializers.PrimaryKeyRelatedField(
        queryset=Test_Type.objects.all(), many=True
    )
    url = serializers.CharField(allow_null=True, default=None)
    tags = TagListSerializerField(required=False)
    push_to_jira = serializers.BooleanField(default=False)

    class Meta:
        model = Finding
        exclude = ["images"]
        extra_kwargs = {
            "reporter": {"default": serializers.CurrentUserDefault()},
        }

    # Overriding this to push add Push to JIRA functionality
    def create(self, validated_data):
        # remove tags from validated data and store them seperately
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        # pop push_to_jira so it won't get send to the model as a field
        push_to_jira = validated_data.pop("push_to_jira")

        # first save, so we have an instance to get push_all_to_jira from
        new_finding = super(TaggitSerializer, self).create(validated_data)

        # TODO: JIRA can we remove this is_push_all_issues, already checked in apiv2 viewset?
        push_to_jira = push_to_jira or jira_helper.is_push_all_issues(new_finding)

        # Allow setting the mitigation date based upon the state of is_Mitigated.
        if new_finding.is_Mitigated:
            new_finding.mitigated = datetime.datetime.now()
            new_finding.mitigated_by = self.context["request"].user
            if settings.USE_TZ:
                new_finding.mitigated = timezone.make_aware(
                    new_finding.mitigated, timezone.get_default_timezone()
                )

        # If we need to push to JIRA, an extra save call is needed.
        # TODO try to combine create and save, but for now I'm just fixing a bug and don't want to change to much
        if push_to_jira or new_finding.is_Mitigated:
            new_finding.save(push_to_jira=push_to_jira)

        # not sure why we are returning a tag_object, but don't want to change too much now as we're just fixing a bug
        tag_object = self._save_tags(new_finding, to_be_tagged)
        return tag_object

    def validate(self, data):
        if (data["active"] or data["verified"]) and data["duplicate"]:
            raise serializers.ValidationError(
                "Duplicate findings cannot be" " verified or active"
            )
        if data["false_p"] and data["verified"]:
            raise serializers.ValidationError(
                "False positive findings cannot " "be verified."
            )

        if "risk_accepted" in data and data["risk_accepted"]:
            test = data["test"]
            # test = Test.objects.get(id=test_id)
            if not test.engagement.product.enable_simple_risk_acceptance:
                raise serializers.ValidationError(
                    "Simple risk acceptance is disabled for this product, use the UI to accept this finding."
                )

        if data["active"] and "risk_accepted" in data and data["risk_accepted"]:
            raise serializers.ValidationError(
                "Active findings cannot " "be risk accepted."
            )

        return data


class FindingTemplateSerializer(serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Finding_Template
        fields = "__all__"


class StubFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stub_Finding
        fields = "__all__"


class StubFindingCreateSerializer(serializers.ModelSerializer):
    test = serializers.PrimaryKeyRelatedField(queryset=Test.objects.all())

    class Meta:
        model = Stub_Finding
        fields = "__all__"
        extra_kwargs = {
            "reporter": {"default": serializers.CurrentUserDefault()},
        }


class ScanSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanSettings
        fields = "__all__"


class ScanSettingsCreateSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    data = serializers.DateTimeField(required=False)

    class Meta:
        model = ScanSettings
        fields = "__all__"


class IPScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPScan
        fields = "__all__"


class ScanSerializer(serializers.ModelSerializer):
    # scan_settings_link = serializers.PrimaryKeyRelatedField(
    #     read_only=True,
    #     source='scan_settings')
    # scan_settings = serializers.PrimaryKeyRelatedField(
    #     queryset=ScanSettings.objects.all(),
    #     write_only=True,
    #     )
    # ipscan_links = serializers.PrimaryKeyRelatedField(
    #     read_only=True,
    #     many=True,
    #     source='ipscan_set')

    class Meta:
        model = Scan
        fields = "__all__"


class ImportScanSerializer(serializers.Serializer):
    scan_date = serializers.DateField(default=datetime.date.today)

    minimum_severity = serializers.ChoiceField(choices=SEVERITY_CHOICES, default="Info")
    active = serializers.BooleanField(default=True)
    verified = serializers.BooleanField(default=True)
    scan_type = serializers.ChoiceField(choices=ImportScanForm.SORTED_SCAN_TYPE_CHOICES)
    endpoint_to_add = serializers.PrimaryKeyRelatedField(
        queryset=Endpoint.objects.all(), required=False, default=None
    )
    test_type = serializers.CharField(required=False)
    file = serializers.FileField(required=False)
    engagement = serializers.PrimaryKeyRelatedField(queryset=Engagement.objects.all())
    lead = serializers.PrimaryKeyRelatedField(
        allow_null=True, default=None, queryset=User.objects.all()
    )
    tags = TagListSerializerField(required=False)
    close_old_findings = serializers.BooleanField(required=False, default=False)
    push_to_jira = serializers.BooleanField(default=False)
    environment = serializers.CharField(required=False)

    # class Meta:
    #     model = Test
    #     # fields = '__all__'
    #     exclude = ['target_start', 'target_end']

    def save(self, push_to_jira=False):
        data = self.validated_data
        close_old_findings = data["close_old_findings"]
        active = data["active"]
        verified = data["verified"]
        test_type, created = Test_Type.objects.get_or_create(
            name=data.get("test_type", data["scan_type"])
        )
        endpoint_to_add = data["endpoint_to_add"]
        scan_date = data["scan_date"]
        scan_date_time = datetime.datetime.combine(scan_date, timezone.now().time())
        if settings.USE_TZ:
            scan_date_time = timezone.make_aware(
                scan_date_time, timezone.get_default_timezone()
            )

        version = ""
        if "version" in data:
            version = data["version"]
        # Will save in the provided environment or in the `Development` one if absent
        environment_name = data.get("environment", "Development")
        environment = Development_Environment.objects.get(name=environment_name)

        test = Test(
            engagement=data["engagement"],
            lead=data["lead"],
            test_type=test_type,
            target_start=data["scan_date"],
            target_end=data["scan_date"],
            environment=environment,
            percent_complete=100,
            version=version,
        )
        try:
            test.full_clean()
        except ValidationError:
            pass

        if "tags" in data:
            logger.debug("import scan tags: %s", data["tags"])
            test.tags = data["tags"]

        test.save()
        # return the id of the created test, can't find a better way because this is not a ModelSerializer....
        self.fields["test"] = serializers.IntegerField(read_only=True, default=test.id)

        test.engagement.updated = max_safe([scan_date_time, test.engagement.updated])

        if test.engagement.engagement_type == "CI/CD":
            test.engagement.target_end = max_safe(
                [scan_date, test.engagement.target_end]
            )

        test.engagement.save()

        try:
            parser = import_parser_factory(
                data.get("file", None),
                test,
                active,
                verified,
                data["scan_type"],
            )
            parser_findings = parser.get_findings(data.get("file", None), test)
        except ValueError:
            raise Exception("FileParser ValueError")
        except:
            raise Exception(
                "Error while parsing the report, did you specify the correct scan type ?"
            )

        new_findings = []
        skipped_hashcodes = []
        try:
            items = parser_findings
            logger.debug("starting import of %i items.", len(items))
            i = 0
            for item in items:
                sev = item.severity
                if sev == "Information" or sev == "Informational":
                    sev = "Info"

                item.severity = sev

                if (
                    Finding.SEVERITIES[sev]
                    > Finding.SEVERITIES[data["minimum_severity"]]
                ):
                    continue

                item.test = test
                item.reporter = self.context["request"].user
                item.last_reviewed = timezone.now()
                item.last_reviewed_by = self.context["request"].user
                item.active = data["active"]
                item.verified = data["verified"]
                logger.debug("going to save finding")
                item.save(dedupe_option=False)

                if hasattr(item, "unsaved_req_resp") and len(item.unsaved_req_resp) > 0:
                    for req_resp in item.unsaved_req_resp:
                        burp_rr = BurpRawRequestResponse(
                            finding=item,
                            burpRequestBase64=base64.b64encode(
                                req_resp["req"].encode("utf-8")
                            ),
                            burpResponseBase64=base64.b64encode(
                                req_resp["resp"].encode("utf-8")
                            ),
                        )
                        burp_rr.clean()
                        burp_rr.save()

                if (
                    item.unsaved_request is not None
                    and item.unsaved_response is not None
                ):
                    burp_rr = BurpRawRequestResponse(
                        finding=item,
                        burpRequestBase64=base64.b64encode(
                            item.unsaved_request.encode()
                        ),
                        burpResponseBase64=base64.b64encode(
                            item.unsaved_response.encode()
                        ),
                    )
                    burp_rr.clean()
                    burp_rr.save()

                for endpoint in item.unsaved_endpoints:
                    ep, created = Endpoint.objects.get_or_create(
                        protocol=endpoint.protocol,
                        host=endpoint.host,
                        path=endpoint.path,
                        query=endpoint.query,
                        fragment=endpoint.fragment,
                        product=test.engagement.product,
                    )
                    eps, created = Endpoint_Status.objects.get_or_create(
                        finding=item, endpoint=ep
                    )
                    ep.endpoint_status.add(eps)
                    item.endpoint_status.add(eps)
                    item.endpoints.add(ep)
                if endpoint_to_add:
                    item.endpoints.add(endpoint_to_add)
                    eps, created = Endpoint_Status.objects.get_or_create(
                        finding=item, endpoint=endpoint_to_add
                    )
                    endpoint_to_add.endpoint_status.add(eps)
                    item.endpoint_status.add(eps)
                if item.unsaved_tags is not None:
                    item.tags = item.unsaved_tags

                item.save(push_to_jira=push_to_jira)
                new_findings.append(item)

        except SyntaxError:
            raise Exception("Parser SyntaxError")

        old_findings = []
        if close_old_findings:
            # Close old active findings that are not reported by this scan.
            new_hash_codes = test.finding_set.values("hash_code")

            if test.engagement.deduplication_on_engagement:
                old_findings = (
                    Finding.objects.exclude(test=test)
                    .exclude(hash_code__in=new_hash_codes)
                    .exclude(hash_code__in=skipped_hashcodes)
                    .filter(
                        test__engagement=test.engagement,
                        test__test_type=test_type,
                        active=True,
                    )
                )
            else:
                old_findings = (
                    Finding.objects.exclude(test=test)
                    .exclude(hash_code__in=new_hash_codes)
                    .exclude(hash_code__in=skipped_hashcodes)
                    .filter(
                        test__engagement__product=test.engagement.product,
                        test__test_type=test_type,
                        active=True,
                    )
                )

            for old_finding in old_findings:
                old_finding.active = False
                old_finding.mitigated = datetime.datetime.combine(
                    test.target_start, timezone.now().time()
                )
                if settings.USE_TZ:
                    old_finding.mitigated = timezone.make_aware(
                        old_finding.mitigated, timezone.get_default_timezone()
                    )
                old_finding.mitigated_by = self.context["request"].user
                old_finding.notes.create(
                    author=self.context["request"].user,
                    entry="This finding has been automatically closed"
                    " as it is not present anymore in recent scans.",
                )
                endpoint_status = old_finding.endpoint_status.all()
                for status in endpoint_status:
                    status.mitigated_by = self.context["request"].user
                    status.mitigated_time = timezone.now()
                    status.mitigated = True
                    status.last_modified = timezone.now()
                    status.save()

                old_finding.tags.add("stale")
                old_finding.save(dedupe_option=False)

        logger.debug("done importing findings")

        title = (
            "Test created for "
            + str(test.engagement.product)
            + ": "
            + str(test.engagement.name)
            + ": "
            + str(test)
        )
        create_notification(
            event="test_added",
            title=title,
            test=test,
            engagement=test.engagement,
            product=test.engagement.product,
            url=reverse("view_test", args=(test.id,)),
        )

        updated_count = len(new_findings) + len(old_findings)
        if updated_count > 0:
            title = (
                "Created "
                + str(updated_count)
                + " findings for "
                + str(test.engagement.product)
                + ": "
                + str(test.engagement.name)
                + ": "
                + str(test)
            )
            create_notification(
                event="scan_added",
                title=title,
                findings_new=new_findings,
                findings_mitigated=old_findings,
                finding_count=updated_count,
                test=test,
                engagement=test.engagement,
                product=test.engagement.product,
                url=reverse("view_test", args=(test.id,)),
            )
        logger.debug("returning test instance")
        return test

    def validate(self, data):
        scan_type = data.get("scan_type")
        file = data.get("file")
        if not file and requires_file(scan_type):
            raise serializers.ValidationError(
                "Uploading a Report File is required for {}".format(scan_type)
            )
        if file and is_scan_file_too_large(file):
            raise serializers.ValidationError(
                "Report file is too large. Maximum supported size is {} MB".format(
                    settings.SCAN_FILE_MAX_SIZE
                )
            )
        return data

    def validate_scan_data(self, value):
        if value.date() > datetime.today().date():
            raise serializers.ValidationError("The date cannot be in the future!")
        return value


class ReImportScanSerializer(TaggitSerializer, serializers.Serializer):
    scan_date = serializers.DateField()
    minimum_severity = serializers.ChoiceField(choices=SEVERITY_CHOICES, default="Info")
    active = serializers.BooleanField(default=True)
    verified = serializers.BooleanField(default=True)
    scan_type = serializers.ChoiceField(choices=ImportScanForm.SORTED_SCAN_TYPE_CHOICES)
    endpoint_to_add = serializers.PrimaryKeyRelatedField(
        queryset=Endpoint.objects.all(), default=None, required=False
    )
    file = serializers.FileField(required=False)
    test = serializers.PrimaryKeyRelatedField(queryset=Test.objects.all())
    push_to_jira = serializers.BooleanField(default=False)
    # Close the old findings if the parameter is not provided. This is to
    # mentain the old API behavior after reintroducing the close_old_findings parameter
    # also for ReImport.
    close_old_findings = serializers.BooleanField(required=False, default=True)

    def save(self, push_to_jira=False):
        data = self.validated_data
        test = data["test"]
        scan_type = data["scan_type"]
        endpoint_to_add = data["endpoint_to_add"]
        min_sev = data["minimum_severity"]
        scan_date = data["scan_date"]
        close_old_findings = data["close_old_findings"]
        scan_date_time = datetime.datetime.combine(scan_date, timezone.now().time())
        if settings.USE_TZ:
            scan_date_time = timezone.make_aware(
                scan_date_time, timezone.get_default_timezone()
            )
        verified = data["verified"]
        active = data["active"]
        version = None
        if "version" in data:
            version = data["version"]

        try:
            parser = import_parser_factory(
                data.get("file", None), test, active, verified, data["scan_type"]
            )
            parser_findings = parser.get_findings(data.get("file", None), test)
        except ValueError:
            raise Exception("Parser ValueError")
        except:
            raise Exception(
                "Error while parsing the report, did you specify the correct scan type ?"
            )

        try:
            items = parser_findings
            original_items = list(test.finding_set.all())
            new_items = []
            mitigated_count = 0
            finding_count = 0
            finding_added_count = 0
            reactivated_count = 0
            reactivated_items = []
            unchanged_count = 0
            unchanged_items = []

            logger.debug("starting reimport of %i items.", len(items))
            i = 0
            for item in items:
                sev = item.severity

                if sev == "Information" or sev == "Informational":
                    sev = "Info"

                if Finding.SEVERITIES[sev] > Finding.SEVERITIES[min_sev]:
                    continue

                # existing findings may be from before we had component_name/version fields
                component_name = (
                    item.component_name if hasattr(item, "component_name") else None
                )
                component_version = (
                    item.component_version
                    if hasattr(item, "component_version")
                    else None
                )

                from titlecase import titlecase

                item.title = titlecase(item.title)
                if scan_type == "Veracode Scan" or scan_type == "Arachni Scan":
                    findings = Finding.objects.filter(
                        title=item.title,
                        test=test,
                        severity=sev,
                        numerical_severity=Finding.get_numerical_severity(sev),
                        description=item.description,
                    ).all()
                else:
                    findings = Finding.objects.filter(
                        title=item.title,
                        test=test,
                        severity=sev,
                        numerical_severity=Finding.get_numerical_severity(sev),
                    ).all()

                # some parsers generate 1 finding for each vulnerable file for each vulnerability
                # i.e
                # #: title                     : sev : file_path
                # 1: CVE-2020-1234 jquery      : 1   : /file1.jar
                # 2: CVE-2020-1234 jquery      : 1   : /file2.jar
                #
                # if we don't filter on file_path, we would find 2 existing findings
                # and the logic below will get confused and map all incoming findings
                # from the reimport on the first finding
                #
                # for Anchore we fix this here, we may need a broader fix (and testcases)
                # or we may need to change the matching logic here to use the same logic
                # as the deduplication logic (hashcode fields)

                if scan_type == "Anchore Engine Scan":
                    if item.file_path:
                        findings = findings.filter(file_path=item.file_path)

                if findings:
                    # existing finding found
                    finding = findings[0]
                    if finding.mitigated or finding.is_Mitigated:
                        logger.debug(
                            "%i: reactivating: %i:%s:%s:%s",
                            i,
                            finding.id,
                            finding,
                            finding.component_name,
                            finding.component_version,
                        )
                        finding.mitigated = None
                        finding.is_Mitigated = False
                        finding.mitigated_by = None
                        finding.active = True
                        finding.verified = verified

                        # existing findings may be from before we had component_name/version fields
                        finding.component_name = (
                            finding.component_name
                            if finding.component_name
                            else component_name
                        )
                        finding.component_version = (
                            finding.component_version
                            if finding.component_version
                            else component_version
                        )

                        # don't dedupe before endpoints are added
                        finding.save(dedupe_option=False)
                        note = Notes(
                            entry="Re-activated by %s re-upload." % scan_type,
                            author=self.context["request"].user,
                        )
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
                        logger.debug(
                            "%i: updating existing finding: %i:%s:%s:%s",
                            i,
                            finding.id,
                            finding,
                            finding.component_name,
                            finding.component_version,
                        )
                        if not finding.component_name or not finding.component_version:
                            finding.component_name = (
                                finding.component_name
                                if finding.component_name
                                else component_name
                            )
                            finding.component_version = (
                                finding.component_version
                                if finding.component_version
                                else component_version
                            )
                            finding.save(dedupe_option=False)

                        unchanged_items.append(finding)
                        unchanged_count += 1
                else:
                    # no existing finding found
                    item.test = test
                    item.reporter = self.context["request"].user
                    item.last_reviewed = timezone.now()
                    item.last_reviewed_by = self.context["request"].user
                    item.verified = verified
                    item.active = active
                    # Save it. Don't dedupe before endpoints are added.
                    item.save(dedupe_option=False)
                    logger.debug(
                        "%i: creating new finding: %i:%s:%s:%s",
                        i,
                        item.id,
                        item,
                        item.component_name,
                        item.component_version,
                    )
                    deduplicationLogger.debug(
                        "reimport found multiple identical existing findings for %i, a non-exact match. these are ignored and a new finding has been created",
                        item.id,
                    )
                    finding_added_count += 1
                    new_items.append(item)
                    finding = item

                    if hasattr(item, "unsaved_req_resp"):
                        for req_resp in item.unsaved_req_resp:
                            burp_rr = BurpRawRequestResponse(
                                finding=finding,
                                burpRequestBase64=base64.b64encode(
                                    req_resp["req"].encode("utf-8")
                                ),
                                burpResponseBase64=base64.b64encode(
                                    req_resp["resp"].encode("utf-8")
                                ),
                            )
                            burp_rr.clean()
                            burp_rr.save()

                    if item.unsaved_request and item.unsaved_response:
                        burp_rr = BurpRawRequestResponse(
                            finding=finding,
                            burpRequestBase64=base64.b64encode(
                                item.unsaved_request.encode()
                            ),
                            burpResponseBase64=base64.b64encode(
                                item.unsaved_response.encode()
                            ),
                        )
                        burp_rr.clean()
                        burp_rr.save()

                # for existing findings: make sure endpoints are present or created
                if finding:
                    finding_count += 1
                    for endpoint in item.unsaved_endpoints:
                        ep, created = Endpoint.objects.get_or_create(
                            protocol=endpoint.protocol,
                            host=endpoint.host,
                            path=endpoint.path,
                            query=endpoint.query,
                            fragment=endpoint.fragment,
                            product=test.engagement.product,
                        )
                        eps, created = Endpoint_Status.objects.get_or_create(
                            finding=finding, endpoint=ep
                        )
                        ep.endpoint_status.add(eps)
                        finding.endpoints.add(ep)
                        finding.endpoint_status.add(eps)
                    if endpoint_to_add:
                        eps, created = Endpoint_Status.objects.get_or_create(
                            finding=finding, endpoint=endpoint_to_add
                        )
                        finding.endpoints.add(endpoint_to_add)
                        endpoint_to_add.endpoint_status.add(eps)
                        finding.endpoint_status.add(eps)
                    if item.unsaved_tags:
                        finding.tags = item.unsaved_tags

                    # existing findings may be from before we had component_name/version fields
                    finding.component_name = (
                        finding.component_name
                        if finding.component_name
                        else component_name
                    )
                    finding.component_version = (
                        finding.component_version
                        if finding.component_version
                        else component_version
                    )

                    finding.save(push_to_jira=push_to_jira)

            to_mitigate = (
                set(original_items) - set(reactivated_items) - set(unchanged_items)
            )
            mitigated_findings = []
            if close_old_findings:
                for finding in to_mitigate:
                    if not finding.mitigated or not finding.is_Mitigated:
                        logger.debug("mitigating finding: %i:%s", finding.id, finding)
                        finding.mitigated = scan_date_time
                        finding.is_Mitigated = True
                        finding.mitigated_by = self.context["request"].user
                        finding.active = False

                        endpoint_status = finding.endpoint_status.all()
                        for status in endpoint_status:
                            status.mitigated_by = self.context["request"].user
                            status.mitigated_time = timezone.now()
                            status.mitigated = True
                            status.last_modified = timezone.now()
                            status.save()

                        # don't try to dedupe findings that we are closing
                        finding.save(push_to_jira=push_to_jira, dedupe_option=False)
                        note = Notes(
                            entry="Mitigated by %s re-upload." % scan_type,
                            author=self.context["request"].user,
                        )
                        note.save()
                        finding.notes.add(note)
                        mitigated_findings.append(finding)
                        mitigated_count += 1

            untouched = set(unchanged_items) - set(to_mitigate)

            test.updated = max_safe([scan_date_time, test.updated])
            test.engagement.updated = max_safe(
                [scan_date_time, test.engagement.updated]
            )

            if test.engagement.engagement_type == "CI/CD":
                test.target_end = max_safe([scan_date_time, test.target_end])
                test.engagement.target_end = max_safe(
                    [scan_date, test.engagement.target_end]
                )

            if version:
                test.version = version
            test.save()
            test.engagement.save()

            updated_count = mitigated_count + reactivated_count + len(new_items)
            if updated_count > 0:
                # new_items = original_items
                title = (
                    "Updated "
                    + str(updated_count)
                    + " findings for "
                    + str(test.engagement.product)
                    + ": "
                    + str(test.engagement.name)
                    + ": "
                    + str(test)
                )
                create_notification(
                    event="scan_added",
                    title=title,
                    findings_new=new_items,
                    findings_mitigated=mitigated_findings,
                    findings_reactivated=reactivated_items,
                    finding_count=updated_count,
                    test=test,
                    engagement=test.engagement,
                    product=test.engagement.product,
                    findings_untouched=untouched,
                    url=reverse("view_test", args=(test.id,)),
                )

        except SyntaxError:
            raise Exception("Parser SyntaxError")

        return test

    def validate(self, data):
        scan_type = data.get("scan_type")
        file = data.get("file")
        if not file and requires_file(scan_type):
            raise serializers.ValidationError(
                "Uploading a Report File is required for {}".format(scan_type)
            )
        if file and is_scan_file_too_large(file):
            raise serializers.ValidationError(
                "Report file is too large. Maximum supported size is {} MB".format(
                    settings.SCAN_FILE_MAX_SIZE
                )
            )
        return data

    def validate_scan_data(self, value):
        if value.date() > datetime.today().date():
            raise serializers.ValidationError("The date cannot be in the future!")
        return value


class AddNewNoteOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notes
        fields = ["entry", "private", "note_type"]


class AddNewFileOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = "__all__"


class FindingToFindingImagesSerializer(serializers.Serializer):
    finding_id = serializers.PrimaryKeyRelatedField(
        queryset=Finding.objects.all(), many=False, allow_null=True
    )
    images = FindingImageSerializer(many=True)


class FindingToNotesSerializer(serializers.Serializer):
    finding_id = serializers.PrimaryKeyRelatedField(
        queryset=Finding.objects.all(), many=False, allow_null=True
    )
    notes = NoteSerializer(many=True)


class FindingToFilesSerializer(serializers.Serializer):
    finding_id = serializers.PrimaryKeyRelatedField(
        queryset=Finding.objects.all(), many=False, allow_null=True
    )
    files = FileSerializer(many=True)


class ReportGenerateOptionSerializer(serializers.Serializer):
    include_finding_notes = serializers.BooleanField(default=False)
    include_finding_images = serializers.BooleanField(default=False)
    include_executive_summary = serializers.BooleanField(default=False)
    include_table_of_contents = serializers.BooleanField(default=False)


class ExecutiveSummarySerializer(serializers.Serializer):
    engagement_name = serializers.CharField(max_length=200)
    engagement_target_start = serializers.DateField()
    engagement_target_end = serializers.DateField()
    test_type_name = serializers.CharField(max_length=200)
    test_target_start = serializers.DateTimeField()
    test_target_end = serializers.DateTimeField()
    test_environment_name = serializers.CharField(max_length=200)
    test_strategy_ref = serializers.URLField(
        max_length=200, min_length=None, allow_blank=True
    )
    total_findings = serializers.IntegerField()


class ReportGenerateSerializer(serializers.Serializer):
    executive_summary = ExecutiveSummarySerializer(many=False, allow_null=True)
    product_type = ProductTypeSerializer(many=False, read_only=True)
    product = ProductSerializer(many=False, read_only=True)
    engagement = EngagementSerializer(many=False, read_only=True)
    report_name = serializers.CharField(max_length=200)
    report_info = serializers.CharField(max_length=200)
    test = TestSerializer(many=False, read_only=True)
    endpoint = EndpointSerializer(many=False, read_only=True)
    endpoints = EndpointSerializer(many=True, read_only=True)
    findings = FindingSerializer(many=True, read_only=True)
    user = UserSerializer(many=False, read_only=True)
    team_name = serializers.CharField(max_length=200)
    title = serializers.CharField(max_length=200)
    user_id = serializers.IntegerField()
    host = serializers.CharField(max_length=200)
    finding_images = FindingToFindingImagesSerializer(
        many=True, allow_null=True, required=False
    )
    finding_notes = FindingToNotesSerializer(many=True, allow_null=True, required=False)


class TagSerializer(serializers.Serializer):
    tags = TagListSerializerField(required=True)


class SystemSettingsSerializer(TaggitSerializer, serializers.ModelSerializer):
    class Meta:
        model = System_Settings
        fields = "__all__"


class FindingNoteSerializer(serializers.Serializer):
    note_id = serializers.IntegerField()


class BurpRawRequestResponseSerializer(serializers.Serializer):
    req_resp = RequestResponseSerializerField(required=True)
