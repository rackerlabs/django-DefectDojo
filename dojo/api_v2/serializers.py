from typing import List
from drf_spectacular.utils import extend_schema_field
from drf_yasg.utils import swagger_serializer_method
from rest_framework.fields import DictField

from dojo.endpoint.utils import endpoint_filter
from dojo.models import Finding_Group, Product, Engagement, Test, Finding, \
    User, Stub_Finding, Risk_Acceptance, \
    Finding_Template, Test_Type, Development_Environment, NoteHistory, \
    JIRA_Issue, Tool_Product_Settings, Tool_Configuration, Tool_Type, \
    Product_Type, JIRA_Instance, Endpoint, JIRA_Project, \
    Notes, DojoMeta, Note_Type, App_Analysis, Endpoint_Status, \
    Sonarqube_Issue, Sonarqube_Issue_Transition, Sonarqube_Product, Regulation, \
    System_Settings, FileUpload, SEVERITY_CHOICES, Test_Import, \
    Test_Import_Finding_Action, Product_Type_Member, Product_Member, \
    Product_Group, Product_Type_Group, Dojo_Group, Role, Global_Role, Dojo_Group_Member, \
    Language_Type, Languages

from dojo.forms import ImportScanForm
from dojo.tools.factory import requires_file
from dojo.utils import is_scan_file_too_large
from django.conf import settings
from rest_framework import serializers
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
import datetime
import six
from django.utils.translation import ugettext_lazy as _
import json
import dojo.jira_link.helper as jira_helper
import logging
import tagulous
from dojo.importers.importer.importer import DojoDefaultImporter as Importer
from dojo.importers.reimporter.reimporter import DojoDefaultReImporter as ReImporter
from dojo.authorization.authorization import user_has_permission
from dojo.authorization.roles_permissions import Permissions


logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


@extend_schema_field(serializers.ListField(child=serializers.CharField()))  # also takes basic python types
class TagListSerializerField(serializers.ListField):
    child = serializers.CharField()
    default_error_messages = {
        'not_a_list': _(
            'Expected a list of items but got type "{input_type}".'),
        'invalid_json': _('Invalid json list. A tag list submitted in string'
                          ' form must be valid json.'),
        'not_a_str': _('All list items must be of string type.')
    }
    order_by = None

    def __init__(self, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)

        style = kwargs.pop("style", {})
        kwargs["style"] = {'base_template': 'textarea.html'}
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
                self.fail('invalid_json')

        logger.debug('data as json: %s', data)

        if not isinstance(data, list):
            self.fail('not_a_list', input_type=type(data).__name__)

        # data_safe = []
        for s in data:
            if not isinstance(s, six.string_types):
                self.fail('not_a_str')

            self.child.run_validation(s)

            # if ' ' in s or ',' in s:
            #     s = '"%s"' % s

            # data_safe.append(s)

        # internal_value = ','.join(data_safe)

        internal_value = tagulous.utils.render_tags(data)

        return internal_value
        # return data

    def to_representation(self, value):
        if not isinstance(value, list):
            # we can't use isinstance because TagRelatedManager is non-existing class
            # it cannot be imported or referenced, so we fallback to string comparison
            if type(value).__name__ == 'TagRelatedManager':
                value = value.get_tag_list()
            elif isinstance(value, str):
                value = tagulous.utils.parse_tags(value)
            else:
                raise ValueError('unable to convert %s into list of tags' % type(value).__name__)
        return value


class TaggitSerializer(serializers.Serializer):
    def create(self, validated_data):
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        tag_object = super(TaggitSerializer, self).create(validated_data)

        return self._save_tags(tag_object, to_be_tagged)

    def update(self, instance, validated_data):
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        tag_object = super(TaggitSerializer, self).update(
            instance, validated_data)

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
            return json.dumps(
                self, sort_keys=True, indent=4, separators=(',', ': '))
        else:
            return json.dumps(self)


class RequestResponseSerializerField(serializers.ListSerializer):
    child = DictField(child=serializers.CharField())
    default_error_messages = {
        'not_a_list': _(
            'Expected a list of items but got type "{input_type}".'),
        'invalid_json': _('Invalid json list. A tag list submitted in string'
                        ' form must be valid json.'),
        'not_a_dict': _('All list items must be of dict type with keys \'request\' and \'response\''),
        'not_a_str': _('All values in the dict must be of string type.')
    }
    order_by = None

    def __init__(self, **kwargs):
        pretty_print = kwargs.pop("pretty_print", True)

        style = kwargs.pop("style", {})
        kwargs["style"] = {'base_template': 'textarea.html'}
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
                self.fail('invalid_json')

        if not isinstance(data, list):
            self.fail('not_a_list', input_type=type(data).__name__)
        for s in data:
            if not isinstance(s, dict):
                self.fail('not_a_dict', input_type=type(s).__name__)

            request = s.get('request', None)
            response = s.get('response', None)

            if not isinstance(request, str):
                self.fail('not_a_str', input_type=type(request).__name__)
            if not isinstance(response, str):
                self.fail('not_a_str', input_type=type(request).__name__)

            self.child.run_validation(s)
        return data

    def to_representation(self, value):
        if not isinstance(value, RequestResponseDict):
            if not isinstance(value, list):
                # this will trigger when a queryset is found...
                if self.order_by:
                    burps = value.all().order_by(*self.order_by)
                else:
                    burps = value.all()
                value = [{'request': burp.get_request(), 'response': burp.get_response()} for burp in burps]

        return value


class BurpRawRequestResponseSerializer(serializers.Serializer):
    req_resp = RequestResponseSerializerField(required=True)


class MetaSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(),
                                                 required=False,
                                                 default=None,
                                                 allow_null=True)
    endpoint = serializers.PrimaryKeyRelatedField(queryset=Endpoint.objects.all(),
                                                  required=False,
                                                  default=None,
                                                  allow_null=True)
    finding = serializers.PrimaryKeyRelatedField(queryset=Finding.objects.all(),
                                                  required=False,
                                                  default=None,
                                                  allow_null=True)

    def validate(self, data):
        DojoMeta(**data).clean()
        return data

    class Meta:
        model = DojoMeta
        fields = '__all__'


class ProductMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DojoMeta
        fields = ('name', 'value')


class UserSerializer(serializers.ModelSerializer):
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'last_login', 'is_active', 'is_staff', 'is_superuser')

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        user.set_unusable_password()
        user.save()
        return user


class UserStubSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name')


class RoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = '__all__'


class DojoGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Dojo_Group
        fields = '__all__'


class DojoGroupMemberSerializer(serializers.ModelSerializer):

    class Meta:
        model = Dojo_Group_Member
        fields = '__all__'

    def validate(self, data):
        if self.instance is not None and \
                data.get('group') != self.instance.group and \
                not user_has_permission(self.context['request'].user, data.get('group'), Permissions.Group_Manage_Members):
            raise PermissionDenied('You are not permitted to add a user to this group')

        if self.instance is None or \
                data.get('group') != self.instance.group or \
                data.get('user') != self.instance.user:
            members = Dojo_Group_Member.objects.filter(group=data.get('group'), user=data.get('user'))
            if members.count() > 0:
                raise ValidationError('Dojo_Group_Member already exists')

        if self.instance is not None and not data.get('role').is_owner:
            owners = Dojo_Group_Member.objects.filter(group=data.get('group'), role__is_owner=True).exclude(id=self.instance.id).count()
            if owners < 1:
                raise ValidationError('There must be at least one owner')

        if data.get('role').is_owner and not user_has_permission(self.context['request'].user, data.get('group'), Permissions.Group_Add_Owner):
            raise PermissionDenied('You are not permitted to add a user as Owner to this group')

        return data


class GlobalRoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Global_Role
        fields = '__all__'

    def validate(self, data):
        user = None
        group = None

        if self.instance is not None:
            user = self.instance.user
            group = self.instance.group

        if 'user' in data:
            user = data.get('user')
        if 'group' in data:
            group = data.get('group')

        if user is None and group is None:
            raise ValidationError("Global_Role must have either user or group")
        if user is not None and group is not None:
            raise ValidationError("Global_Role cannot have both user and group")

        return data


class AddUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'username')


class NoteHistorySerializer(serializers.ModelSerializer):
    current_editor = UserStubSerializer(read_only=True)

    class Meta:
        model = NoteHistory
        fields = '__all__'


class NoteSerializer(serializers.ModelSerializer):
    author = UserStubSerializer(
        many=False, read_only=True)
    editor = UserStubSerializer(
        read_only=True, many=False, allow_null=True)

    history = NoteHistorySerializer(read_only=True, many=True)

    def update(self, instance, validated_data):
        instance.entry = validated_data['entry']
        instance.edited = True
        instance.editor = self.context['request'].user
        instance.edit_time = timezone.now()
        history = NoteHistory(
            data=instance.entry,
            time=instance.edit_time,
            current_editor=instance.editor
        )
        history.save()
        instance.history.add(history)
        instance.save()
        return instance

    class Meta:
        model = Notes
        fields = '__all__'


class NoteTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note_Type
        fields = '__all__'


class FileSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=True)

    class Meta:
        model = FileUpload
        fields = '__all__'


class ProductMemberSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product_Member
        fields = '__all__'

    def validate(self, data):
        if self.instance is not None and \
                data.get('product') != self.instance.product and \
                not user_has_permission(self.context['request'].user, data.get('product'), Permissions.Product_Manage_Members):
            raise PermissionDenied('You are not permitted to add a member to this product')

        if self.instance is None or \
                data.get('product') != self.instance.product or \
                data.get('user') != self.instance.user:
            members = Product_Member.objects.filter(product=data.get('product'), user=data.get('user'))
            if members.count() > 0:
                raise ValidationError('Product_Member already exists')

        if data.get('role').is_owner and not user_has_permission(self.context['request'].user, data.get('product'), Permissions.Product_Member_Add_Owner):
            raise PermissionDenied('You are not permitted to add a member as Owner to this product')

        return data


class ProductGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product_Group
        fields = '__all__'

    def validate(self, data):
        if self.instance is not None and \
                data.get('product') != self.instance.product and \
                not user_has_permission(self.context['request'].user, data.get('product'), Permissions.Product_Group_Add):
            raise PermissionDenied('You are not permitted to add a group to this product')

        if self.instance is None or \
                data.get('product') != self.instance.product or \
                data.get('group') != self.instance.group:
            members = Product_Group.objects.filter(product=data.get('product'), group=data.get('group'))
            if members.count() > 0:
                raise ValidationError('Product_Group already exists')

        if data.get('role').is_owner and not user_has_permission(self.context['request'].user, data.get('product'), Permissions.Product_Group_Add_Owner):
            raise PermissionDenied('You are not permitted to add a group as Owner to this product')

        return data


class ProductTypeMemberSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product_Type_Member
        fields = '__all__'

    def validate(self, data):
        if self.instance is not None and \
                data.get('product_type') != self.instance.product_type and \
                not user_has_permission(self.context['request'].user, data.get('product_type'), Permissions.Product_Type_Manage_Members):
            raise PermissionDenied('You are not permitted to add a member to this product type')

        if self.instance is None or \
                data.get('product_type') != self.instance.product_type or \
                data.get('user') != self.instance.user:
            members = Product_Type_Member.objects.filter(product_type=data.get('product_type'), user=data.get('user'))
            if members.count() > 0:
                raise ValidationError('Product_Type_Member already exists')

        if self.instance is not None and not data.get('role').is_owner:
            owners = Product_Type_Member.objects.filter(product_type=data.get('product_type'), role__is_owner=True).exclude(id=self.instance.id).count()
            if owners < 1:
                raise ValidationError('There must be at least one owner')

        if data.get('role').is_owner and not user_has_permission(self.context['request'].user, data.get('product_type'), Permissions.Product_Type_Member_Add_Owner):
            raise PermissionDenied('You are not permitted to add a member as Owner to this product type')

        return data


class ProductTypeGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product_Type_Group
        fields = '__all__'

    def validate(self, data):
        if self.instance is not None and \
                data.get('product_type') != self.instance.product_type and \
                not user_has_permission(self.context['request'].user, data.get('product_type'), Permissions.Product_Type_Group_Add):
            raise PermissionDenied('You are not permitted to add a group to this product type')

        if self.instance is None or \
                data.get('product_type') != self.instance.product_type or \
                data.get('group') != self.instance.group:
            members = Product_Type_Group.objects.filter(product_type=data.get('product_type'), group=data.get('group'))
            if members.count() > 0:
                raise ValidationError('Product_Type_Group already exists')

        if data.get('role').is_owner and not user_has_permission(self.context['request'].user, data.get('product_type'), Permissions.Product_Type_Group_Add_Owner):
            raise PermissionDenied('You are not permitted to add a group as Owner to this product type')

        return data


class ProductTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product_Type

        if not settings.FEATURE_AUTHORIZATION_V2:
            exclude = ['members']
            extra_kwargs = {
                'authorized_users': {'queryset': User.objects.exclude(is_staff=True).exclude(is_active=False)}
            }
        else:
            exclude = ['authorized_users']


class EngagementSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Engagement
        fields = '__all__'

    def validate(self, data):
        if self.context['request'].method == 'POST':
            if data['target_start'] > data['target_end']:
                raise serializers.ValidationError(
                    'Your target start date exceeds your target end date')
        return data

    def build_relational_field(self, field_name, relation_info):
        if field_name == 'notes':
            return NoteSerializer, {'many': True, 'read_only': True}
        if field_name == 'files':
            return FileSerializer, {'many': True, 'read_only': True}
        return super().build_relational_field(field_name, relation_info)


class EngagementToNotesSerializer(serializers.Serializer):
    engagement_id = serializers.PrimaryKeyRelatedField(queryset=Engagement.objects.all(), many=False, allow_null=True)
    notes = NoteSerializer(many=True)


class EngagementToFilesSerializer(serializers.Serializer):
    engagement_id = serializers.PrimaryKeyRelatedField(queryset=Engagement.objects.all(), many=False, allow_null=True)
    files = FileSerializer(many=True)


class AppAnalysisSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = App_Analysis
        fields = '__all__'


class ToolTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool_Type
        fields = '__all__'


class RegulationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Regulation
        fields = '__all__'


class ToolConfigurationSerializer(serializers.ModelSerializer):
    configuration_url = serializers.CharField(source='url')

    class Meta:
        model = Tool_Configuration
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
            'ssh': {'write_only': True},
            'api_key': {'write_only': True},
        }


class ToolProductSettingsSerializer(serializers.ModelSerializer):
    setting_url = serializers.CharField(source='url')

    class Meta:
        model = Tool_Product_Settings
        fields = '__all__'


class EndpointStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endpoint_Status
        fields = '__all__'

    def create(self, validated_data):
        endpoint = validated_data['endpoint']
        finding = validated_data['finding']
        status = Endpoint_Status.objects.create(
            finding=finding,
            endpoint=endpoint
        )
        endpoint.endpoint_status.add(status)
        finding.endpoint_status.add(status)
        status.mitigated = validated_data.get('mitigated', False)
        status.false_positive = validated_data.get('false_positive', False)
        status.out_of_scope = validated_data.get('out_of_scope', False)
        status.risk_accepted = validated_data.get('risk_accepted', False)
        status.date = validated_data.get('date', timezone.now())
        status.save()
        return status


class EndpointSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Endpoint
        fields = '__all__'

    def validate(self, data):
        # print('EndpointSerialize.validate')

        if not self.context['request'].method == 'PATCH':
            if 'product' not in data:
                raise serializers.ValidationError('Product is required')
            protocol = data.get('protocol')
            userinfo = data.get('userinfo')
            host = data.get('host')
            port = data.get('port')
            path = data.get('path')
            query = data.get('query')
            fragment = data.get('fragment')
            product = data.get('product')
        else:
            protocol = data.get('protocol', self.instance.protocol)
            userinfo = data.get('userinfo', self.instance.userinfo)
            host = data.get('host', self.instance.host)
            port = data.get('port', self.instance.port)
            path = data.get('path', self.instance.path)
            query = data.get('query', self.instance.query)
            fragment = data.get('fragment', self.instance.fragment)
            if 'product' in data and data['product'] != self.instance.product:
                raise serializers.ValidationError('Change of product is not possible')
            product = self.instance.product

        endpoint_ins = Endpoint(
            protocol=protocol,
            userinfo=userinfo,
            host=host,
            port=port,
            path=path,
            query=query,
            fragment=fragment,
            product=product
        )
        endpoint_ins.clean()  # Run standard validation and clean process; can raise errors

        endpoint = endpoint_filter(
            protocol=endpoint_ins.protocol,
            userinfo=endpoint_ins.userinfo,
            host=endpoint_ins.host,
            port=endpoint_ins.port,
            path=endpoint_ins.path,
            query=endpoint_ins.query,
            fragment=endpoint_ins.fragment,
            product=endpoint_ins.product
        )
        if ((self.context['request'].method in ["PUT", "PATCH"] and
             ((endpoint.count() > 1) or
              (endpoint.count() == 1 and
               endpoint.first().pk != self.instance.pk))) or
                (self.context['request'].method in ["POST"] and endpoint.count() > 0)):
            raise serializers.ValidationError(
                'It appears as though an endpoint with this data already '
                'exists for this product.',
                code='invalid')

        # use clean data
        data['protocol'] = endpoint_ins.protocol
        data['userinfo'] = endpoint_ins.userinfo
        data['host'] = endpoint_ins.host
        data['port'] = endpoint_ins.port
        data['path'] = endpoint_ins.path
        data['query'] = endpoint_ins.query
        data['fragment'] = endpoint_ins.fragment
        data['product'] = endpoint_ins.product

        return data


class JIRAIssueSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JIRA_Issue
        fields = '__all__'

    def get_url(self, obj) -> str:
        return jira_helper.get_jira_issue_url(obj)


class JIRAInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = JIRA_Instance
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
        }


class JIRAProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = JIRA_Project
        fields = '__all__'


class SonarqubeIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sonarqube_Issue
        fields = '__all__'


class SonarqubeIssueTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sonarqube_Issue_Transition
        fields = '__all__'


class SonarqubeProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sonarqube_Product
        fields = '__all__'


class DevelopmentEnvironmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Development_Environment
        fields = '__all__'


class FindingGroupSerializer(serializers.ModelSerializer):
    jira_issue = JIRAIssueSerializer(read_only=True)

    class Meta:
        model = Finding_Group
        fields = ('id', 'name', 'test', 'jira_issue')


class TestSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)
    test_type_name = serializers.ReadOnlyField()
    finding_groups = FindingGroupSerializer(source='finding_group_set', many=True, read_only=True)

    class Meta:
        model = Test
        fields = '__all__'

    def build_relational_field(self, field_name, relation_info):
        if field_name == 'notes':
            return NoteSerializer, {'many': True, 'read_only': True}
        if field_name == 'files':
            return FileSerializer, {'many': True, 'read_only': True}
        return super().build_relational_field(field_name, relation_info)


class TestCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    engagement = serializers.PrimaryKeyRelatedField(
        queryset=Engagement.objects.all())
    notes = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=Notes.objects.all(),
        many=True,
        required=False)
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Test
        fields = '__all__'


class TestTypeSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Test_Type
        fields = '__all__'


class TestToNotesSerializer(serializers.Serializer):
    test_id = serializers.PrimaryKeyRelatedField(queryset=Test.objects.all(), many=False, allow_null=True)
    notes = NoteSerializer(many=True)


class TestToFilesSerializer(serializers.Serializer):
    test_id = serializers.PrimaryKeyRelatedField(queryset=Test.objects.all(), many=False, allow_null=True)
    files = FileSerializer(many=True)


class TestImportFindingActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test_Import_Finding_Action
        fields = '__all__'


class TestImportSerializer(serializers.ModelSerializer):
    # findings = TestImportFindingActionSerializer(source='test_import_finding_action', many=True, read_only=True)
    test_import_finding_action_set = TestImportFindingActionSerializer(many=True, read_only=True)

    class Meta:
        model = Test_Import
        fields = '__all__'


class RiskAcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Risk_Acceptance
        fields = '__all__'


class FindingMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DojoMeta
        fields = ('name', 'value')


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
        fields = ["id", "name", "product", "branch_tag", "build_id", "commit_hash", "version"]


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
        fields = ["id", "title", "test_type", "engagement", "environment", "branch_tag", "build_id", "commit_hash", "version"]


class FindingRelatedFieldsSerializer(serializers.Serializer):
    test = serializers.SerializerMethodField()
    jira = serializers.SerializerMethodField()

    @extend_schema_field(FindingTestSerializer)
    @swagger_serializer_method(FindingTestSerializer)
    def get_test(self, obj):
        return FindingTestSerializer(read_only=True).to_representation(obj.test)

    @extend_schema_field(JIRAIssueSerializer)
    @swagger_serializer_method(JIRAIssueSerializer)
    def get_jira(self, obj):
        issue = jira_helper.get_jira_issue(obj)
        if issue is None:
            return None
        return JIRAIssueSerializer(read_only=True).to_representation(issue)


class FindingSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)
    request_response = serializers.SerializerMethodField()
    accepted_risks = RiskAcceptanceSerializer(many=True, read_only=True, source='risk_acceptance_set')
    push_to_jira = serializers.BooleanField(default=False)
    age = serializers.IntegerField(read_only=True)
    sla_days_remaining = serializers.IntegerField(read_only=True)
    finding_meta = FindingMetaSerializer(read_only=True, many=True)
    related_fields = serializers.SerializerMethodField()
    # for backwards compatibility
    jira_creation = serializers.SerializerMethodField(read_only=True)
    jira_change = serializers.SerializerMethodField(read_only=True)
    display_status = serializers.SerializerMethodField()
    finding_groups = FindingGroupSerializer(source='finding_group_set', many=True, read_only=True)

    class Meta:
        model = Finding
        fields = '__all__'

    @extend_schema_field(serializers.DateTimeField())
    @swagger_serializer_method(serializers.DateTimeField())
    def get_jira_creation(self, obj):
        return jira_helper.get_jira_creation(obj)

    @extend_schema_field(serializers.DateTimeField())
    @swagger_serializer_method(serializers.DateTimeField())
    def get_jira_change(self, obj):
        return jira_helper.get_jira_change(obj)

    @extend_schema_field(FindingRelatedFieldsSerializer)
    @swagger_serializer_method(FindingRelatedFieldsSerializer)
    def get_related_fields(self, obj):
        request = self.context.get('request', None)
        if request is None:
            return None

        query_params = request.query_params
        if query_params.get('related_fields', 'false') == 'true':
            return FindingRelatedFieldsSerializer(required=False).to_representation(obj)
        else:
            return None

    def get_display_status(self, obj) -> str:
        return obj.status()

    # Overriding this to push add Push to JIRA functionality
    def update(self, instance, validated_data):
        # remove tags from validated data and store them seperately
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        # pop push_to_jira so it won't get send to the model as a field
        # TODO: JIRA can we remove this is_push_all_issues, already checked in apiv2 viewset?
        push_to_jira = validated_data.pop('push_to_jira') or jira_helper.is_push_all_issues(instance)

        instance = super(TaggitSerializer, self).update(instance, validated_data)

        # If we need to push to JIRA, an extra save call is needed.
        # Also if we need to update the mitigation date of the finding.
        # TODO try to combine create and save, but for now I'm just fixing a bug and don't want to change to much
        if push_to_jira:
            instance.save(push_to_jira=push_to_jira)

        # not sure why we are returning a tag_object, but don't want to change too much now as we're just fixing a bug
        tag_object = self._save_tags(instance, to_be_tagged)
        return tag_object

    def validate(self, data):
        if self.context['request'].method == 'PATCH':
            is_active = data.get('active', self.instance.active)
            is_verified = data.get('verified', self.instance.verified)
            is_duplicate = data.get('duplicate', self.instance.duplicate)
            is_false_p = data.get('false_p', self.instance.false_p)
            is_risk_accepted = data.get('risk_accepted', self.instance.risk_accepted)
        else:
            is_active = data.get('active', True)
            is_verified = data.get('verified', True)
            is_duplicate = data.get('duplicate', False)
            is_false_p = data.get('false_p', False)
            is_risk_accepted = data.get('risk_accepted', False)

        if ((is_active or is_verified) and is_duplicate):
            raise serializers.ValidationError('Duplicate findings cannot be'
                                              ' verified or active')
        if is_false_p and is_verified:
            raise serializers.ValidationError('False positive findings cannot '
                                              'be verified.')

        if is_risk_accepted and not self.instance.risk_accepted:
            if not self.instance.test.engagement.product.enable_simple_risk_acceptance:
                raise serializers.ValidationError('Simple risk acceptance is disabled for this product, use the UI to accept this finding.')

        if is_active and is_risk_accepted:
            raise serializers.ValidationError('Active findings cannot '
                                        'be risk accepted.')

        return data

    def build_relational_field(self, field_name, relation_info):
        if field_name == 'notes':
            return NoteSerializer, {'many': True, 'read_only': True}
        return super().build_relational_field(field_name, relation_info)

    @extend_schema_field(BurpRawRequestResponseSerializer)
    @swagger_serializer_method(serializer_or_field=BurpRawRequestResponseSerializer)
    def get_request_response(self, obj):
        # burp_req_resp = BurpRawRequestResponse.objects.filter(finding=obj)
        burp_req_resp = obj.burprawrequestresponse_set.all()
        burp_list = []
        for burp in burp_req_resp:
            request = burp.get_request()
            response = burp.get_response()
            burp_list.append({'request': request, 'response': response})
        serialized_burps = BurpRawRequestResponseSerializer({'req_resp': burp_list})
        return serialized_burps.data


class FindingCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    notes = serializers.PrimaryKeyRelatedField(
        read_only=True,
        allow_null=True,
        required=False,
        many=True)
    test = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all())
    thread_id = serializers.IntegerField(default=0)
    found_by = serializers.PrimaryKeyRelatedField(
        queryset=Test_Type.objects.all(),
        many=True)
    url = serializers.CharField(
        allow_null=True,
        default=None)
    tags = TagListSerializerField(required=False)
    push_to_jira = serializers.BooleanField(default=False)

    class Meta:
        model = Finding
        fields = '__all__'
        extra_kwargs = {
            'reporter': {'default': serializers.CurrentUserDefault()},
        }

    # Overriding this to push add Push to JIRA functionality
    def create(self, validated_data):
        # remove tags from validated data and store them seperately
        to_be_tagged, validated_data = self._pop_tags(validated_data)

        # pop push_to_jira so it won't get send to the model as a field
        push_to_jira = validated_data.pop('push_to_jira')

        # first save, so we have an instance to get push_all_to_jira from
        new_finding = super(TaggitSerializer, self).create(validated_data)

        # TODO: JIRA can we remove this is_push_all_issues, already checked in apiv2 viewset?
        push_to_jira = push_to_jira or jira_helper.is_push_all_issues(new_finding)

        # If we need to push to JIRA, an extra save call is needed.
        # TODO try to combine create and save, but for now I'm just fixing a bug and don't want to change to much
        if push_to_jira or new_finding:
            new_finding.save(push_to_jira=push_to_jira)

        # not sure why we are returning a tag_object, but don't want to change too much now as we're just fixing a bug
        tag_object = self._save_tags(new_finding, to_be_tagged)
        return tag_object

    def validate(self, data):
        if ((data['active'] or data['verified']) and data['duplicate']):
            raise serializers.ValidationError('Duplicate findings cannot be'
                                              ' verified or active')
        if data['false_p'] and data['verified']:
            raise serializers.ValidationError('False positive findings cannot '
                                              'be verified.')

        if 'risk_accepted' in data and data['risk_accepted']:
            test = data['test']
            # test = Test.objects.get(id=test_id)
            if not test.engagement.product.enable_simple_risk_acceptance:
                raise serializers.ValidationError('Simple risk acceptance is disabled for this product, use the UI to accept this finding.')

        if data['active'] and 'risk_accepted' in data and data['risk_accepted']:
            raise serializers.ValidationError('Active findings cannot '
                                        'be risk accepted.')

        return data


class FindingTemplateSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Finding_Template
        fields = '__all__'


class StubFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stub_Finding
        fields = '__all__'


class StubFindingCreateSerializer(serializers.ModelSerializer):
    test = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all())

    class Meta:
        model = Stub_Finding
        fields = '__all__'
        extra_kwargs = {
            'reporter': {'default': serializers.CurrentUserDefault()},
        }


class ProductSerializer(TaggitSerializer, serializers.ModelSerializer):
    findings_count = serializers.SerializerMethodField()
    findings_list = serializers.SerializerMethodField()

    tags = TagListSerializerField(required=False)
    product_meta = ProductMetaSerializer(read_only=True, many=True)

    class Meta:
        model = Product
        if not settings.FEATURE_AUTHORIZATION_V2:
            exclude = ['tid', 'updated', 'members']
            extra_kwargs = {
                'authorized_users': {'queryset': User.objects.exclude(is_staff=True).exclude(is_active=False)}
            }
        else:
            exclude = ['tid', 'updated', 'authorized_users']

    def get_findings_count(self, obj) -> int:
        return obj.findings_count

    #  -> List[int] as return type doesn't seem enough for drf-yasg
    @swagger_serializer_method(serializer_or_field=serializers.ListField(child=serializers.IntegerField()))
    def get_findings_list(self, obj) -> List[int]:
        return obj.open_findings_list


class ImportScanSerializer(serializers.Serializer):
    scan_date = serializers.DateField(default=datetime.date.today)

    minimum_severity = serializers.ChoiceField(
        choices=SEVERITY_CHOICES,
        default='Info')
    active = serializers.BooleanField(default=True)
    verified = serializers.BooleanField(default=True)
    scan_type = serializers.ChoiceField(
        choices=ImportScanForm.SORTED_SCAN_TYPE_CHOICES)
    # TODO why do we allow only existing endpoints?
    endpoint_to_add = serializers.PrimaryKeyRelatedField(queryset=Endpoint.objects.all(),
                                                         required=False,
                                                         default=None)
    file = serializers.FileField(required=False)
    engagement = serializers.PrimaryKeyRelatedField(
        queryset=Engagement.objects.all())
    lead = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        default=None,
        queryset=User.objects.all())
    tags = TagListSerializerField(required=False)
    close_old_findings = serializers.BooleanField(required=False, default=False)
    push_to_jira = serializers.BooleanField(default=False)
    environment = serializers.CharField(required=False)
    version = serializers.CharField(required=False)
    build_id = serializers.CharField(required=False)
    branch_tag = serializers.CharField(required=False)
    commit_hash = serializers.CharField(required=False)

    test = serializers.IntegerField(read_only=True)  # not a modelserializer, so can't use related fields

    group_by = serializers.ChoiceField(required=False, choices=Finding_Group.GROUP_BY_OPTIONS, help_text='Choose an option to automatically group new findings by the chosen option.')

    def save(self, push_to_jira=False):
        data = self.validated_data
        close_old_findings = data['close_old_findings']
        active = data['active']
        verified = data['verified']
        minimum_severity = data['minimum_severity']
        scan_type = data['scan_type']
        endpoint_to_add = data['endpoint_to_add']
        scan_date = data['scan_date']
        # Will save in the provided environment or in the `Development` one if absent
        version = data.get('version', None)
        build_id = data.get('build_id', None)
        branch_tag = data.get('branch_tag', None)
        commit_hash = data.get('commit_hash', None)

        environment_name = data.get('environment', 'Development')
        environment = Development_Environment.objects.get(name=environment_name)
        tags = None
        if 'tags' in data:
            logger.debug('import scan tags: %s', data['tags'])
            tags = data['tags']

        engagement = data['engagement']
        lead = data['lead']

        scan = data.get('file', None)
        endpoints_to_add = [endpoint_to_add] if endpoint_to_add else None

        group_by = data.get('group_by', None)

        importer = Importer()
        try:
            test, finding_count, closed_finding_count = importer.import_scan(scan, scan_type, engagement, lead, environment,
                                                                             active=active, verified=verified, tags=tags,
                                                                             minimum_severity=minimum_severity,
                                                                             endpoints_to_add=endpoints_to_add,
                                                                             scan_date=scan_date, version=version,
                                                                             branch_tag=branch_tag, build_id=build_id,
                                                                             commit_hash=commit_hash,
                                                                             push_to_jira=push_to_jira,
                                                                             close_old_findings=close_old_findings,
                                                                             group_by=group_by)
        # convert to exception otherwise django rest framework will swallow them as 400 error
        # exceptions are already logged in the importer
        except SyntaxError as se:
            raise Exception(se)
        except ValueError as ve:
            raise Exception(ve)

        # return the id of the created test, can't find a better way because this is not a ModelSerializer....
        self.fields['test'] = serializers.IntegerField(read_only=True, default=test.id)

        return test

    def validate(self, data):
        scan_type = data.get("scan_type")
        file = data.get("file")
        if not file and requires_file(scan_type):
            raise serializers.ValidationError('Uploading a Report File is required for {}'.format(scan_type))
        if file and is_scan_file_too_large(file):
            raise serializers.ValidationError(
                'Report file is too large. Maximum supported size is {} MB'.format(settings.SCAN_FILE_MAX_SIZE))
        return data

    def validate_scan_data(self, value):
        if value.date() > datetime.today().date():
            raise serializers.ValidationError(
                'The date cannot be in the future!')
        return value


class ReImportScanSerializer(TaggitSerializer, serializers.Serializer):
    scan_date = serializers.DateField()
    minimum_severity = serializers.ChoiceField(
        choices=SEVERITY_CHOICES,
        default='Info')
    active = serializers.BooleanField(default=True)
    verified = serializers.BooleanField(default=True)
    scan_type = serializers.ChoiceField(
        choices=ImportScanForm.SORTED_SCAN_TYPE_CHOICES)
    endpoint_to_add = serializers.PrimaryKeyRelatedField(queryset=Endpoint.objects.all(),
                                                          default=None,
                                                          required=False)
    file = serializers.FileField(required=False)
    test = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all())
    push_to_jira = serializers.BooleanField(default=False)
    # Close the old findings if the parameter is not provided. This is to
    # mentain the old API behavior after reintroducing the close_old_findings parameter
    # also for ReImport.
    close_old_findings = serializers.BooleanField(required=False, default=True)
    version = serializers.CharField(required=False)
    build_id = serializers.CharField(required=False)
    branch_tag = serializers.CharField(required=False)
    commit_hash = serializers.CharField(required=False)

    group_by = serializers.ChoiceField(required=False, choices=Finding_Group.GROUP_BY_OPTIONS, help_text='Choose an option to automatically group new findings by the chosen option.')

    def save(self, push_to_jira=False):
        logger.debug('push_to_jira: %s', push_to_jira)
        data = self.validated_data
        test = data['test']
        scan_type = data['scan_type']
        endpoint_to_add = data['endpoint_to_add']
        minimum_severity = data['minimum_severity']
        scan_date = data['scan_date']
        close_old_findings = data['close_old_findings']
        verified = data['verified']
        active = data['active']
        version = data.get('version', None)
        build_id = data.get('build_id', None)
        branch_tag = data.get('branch_tag', None)
        commit_hash = data.get('commit_hash', None)

        scan = data.get('file', None)
        endpoints_to_add = [endpoint_to_add] if endpoint_to_add else None

        group_by = data.get('group_by', None)

        reimporter = ReImporter()
        try:
            test, finding_count, new_finding_count, closed_finding_count, reactivated_finding_count, untouched_finding_count = \
                reimporter.reimport_scan(scan, scan_type, test, active=active, verified=verified,
                                            tags=None, minimum_severity=minimum_severity,
                                            endpoints_to_add=endpoints_to_add, scan_date=scan_date,
                                            version=version, branch_tag=branch_tag, build_id=build_id,
                                            commit_hash=commit_hash, push_to_jira=push_to_jira,
                                            close_old_findings=close_old_findings,
                                            group_by=group_by)
        # convert to exception otherwise django rest framework will swallow them as 400 error
        # exceptions are already logged in the importer
        except SyntaxError as se:
            raise Exception(se)
        except ValueError as ve:
            raise Exception(ve)

        return test

    def validate(self, data):
        scan_type = data.get("scan_type")
        file = data.get("file")
        if not file and requires_file(scan_type):
            raise serializers.ValidationError('Uploading a Report File is required for {}'.format(scan_type))
        if file and is_scan_file_too_large(file):
            raise serializers.ValidationError(
                'Report file is too large. Maximum supported size is {} MB'.format(settings.SCAN_FILE_MAX_SIZE))
        return data

    def validate_scan_data(self, value):
        if value.date() > datetime.today().date():
            raise serializers.ValidationError(
                'The date cannot be in the future!')
        return value


class LanguageTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Language_Type
        fields = '__all__'


class LanguageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Languages
        fields = '__all__'


class ImportLanguagesSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=True)
    file = serializers.FileField(required=True)

    def save(self):
        data = self.validated_data
        product = data['product']
        languages = data['file']

        try:
            data = languages.read()
            try:
                deserialized = json.loads(str(data, 'utf-8'))
            except:
                deserialized = json.loads(data)
        except:
            raise Exception("Invalid format")

        Languages.objects.filter(product=product).delete()

        for name in deserialized:
            if name not in ['header', 'SUM']:
                element = deserialized[name]

                try:
                    language_type, created = Language_Type.objects.get_or_create(language=name)
                except Language_Type.MultipleObjectsReturned:
                    language_type = Language_Type.objects.filter(language=name).first()

                language = Languages()
                language.product = product
                language.language = language_type
                language.files = element.get('nFiles', 0)
                language.blank = element.get('blank', 0)
                language.comment = element.get('comment', 0)
                language.code = element.get('code', 0)
                language.save()

    def validate(self, data):
        if is_scan_file_too_large(data['file']):
            raise serializers.ValidationError(
                'File is too large. Maximum supported size is {} MB'.format(settings.SCAN_FILE_MAX_SIZE))
        return data


class AddNewNoteOptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Notes
        fields = ['entry', 'private', 'note_type']


class AddNewFileOptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = FileUpload
        fields = '__all__'


class FindingToNotesSerializer(serializers.Serializer):
    finding_id = serializers.PrimaryKeyRelatedField(queryset=Finding.objects.all(), many=False, allow_null=True)
    notes = NoteSerializer(many=True)


class FindingToFilesSerializer(serializers.Serializer):
    finding_id = serializers.PrimaryKeyRelatedField(queryset=Finding.objects.all(), many=False, allow_null=True)
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
    test_strategy_ref = serializers.URLField(max_length=200, min_length=None, allow_blank=True)
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
    user = UserStubSerializer(many=False, read_only=True)
    team_name = serializers.CharField(max_length=200)
    title = serializers.CharField(max_length=200)
    user_id = serializers.IntegerField()
    host = serializers.CharField(max_length=200)
    finding_notes = FindingToNotesSerializer(many=True, allow_null=True, required=False)


class TagSerializer(serializers.Serializer):
    tags = TagListSerializerField(required=True)


class SystemSettingsSerializer(TaggitSerializer, serializers.ModelSerializer):

    class Meta:
        model = System_Settings
        fields = '__all__'


class FindingNoteSerializer(serializers.Serializer):
    note_id = serializers.IntegerField()
