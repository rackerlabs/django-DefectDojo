import collections
from dojo.finding.helper import ACCEPTED_FINDINGS_QUERY, CLOSED_FINDINGS_QUERY, FALSE_POSITIVE_FINDINGS_QUERY, INACTIVE_FINDINGS_QUERY, OPEN_FINDINGS_QUERY, OUT_OF_SCOPE_FINDINGS_QUERY, VERIFIED_FINDINGS_QUERY
import logging
from datetime import timedelta, datetime
from django import forms
from django.apps import apps
from auditlog.models import LogEntry
from django.conf import settings
import six
from django.utils.translation import ugettext_lazy as _
from django_filters import FilterSet, CharFilter, OrderingFilter, \
    ModelMultipleChoiceFilter, ModelChoiceFilter, MultipleChoiceFilter, \
    BooleanFilter, NumberFilter, DateFilter
from django_filters import rest_framework as filters
from django_filters.filters import ChoiceFilter, _truncate
import pytz
from django.db.models import Q
from dojo.models import Dojo_User, Finding_Group, Product_Type, Finding, Product, Test_Import, Test_Type, \
    Endpoint, Development_Environment, Finding_Template, Note_Type, \
    Engagement_Survey, Question, TextQuestion, ChoiceQuestion, Endpoint_Status, Engagement, \
    ENGAGEMENT_STATUS_CHOICES, Test, App_Analysis, SEVERITY_CHOICES, Dojo_Group
from dojo.utils import get_system_setting
from django.contrib.contenttypes.models import ContentType
import tagulous
# from tagulous.forms import TagWidget
# import tagulous
from dojo.authorization.roles_permissions import Permissions
from dojo.product_type.queries import get_authorized_product_types
from dojo.product.queries import get_authorized_products
from dojo.engagement.queries import get_authorized_engagements
from dojo.test.queries import get_authorized_tests
from dojo.finding.queries import get_authorized_findings
from dojo.endpoint.queries import get_authorized_endpoints
from dojo.finding_group.queries import get_authorized_finding_groups
from django.forms import HiddenInput

logger = logging.getLogger(__name__)

local_tz = pytz.timezone(get_system_setting('time_zone'))

BOOLEAN_CHOICES = (('false', 'No'), ('true', 'Yes'),)
EARLIEST_FINDING = None


def custom_filter(queryset, name, value):
    values = value.split(',')
    filter = ('%s__in' % (name))
    return queryset.filter(Q(**{filter: values}))


def now():
    return local_tz.localize(datetime.today())


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class CharFieldInFilter(filters.BaseInFilter, filters.CharFilter):
    def __init__(self, *args, **kwargs):
        super(CharFilter, self).__init__(*args, **kwargs)


class FindingStatusFilter(ChoiceFilter):
    def any(self, qs, name):
        return qs

    def open(self, qs, name):
        return qs.filter(OPEN_FINDINGS_QUERY)

    def verified(self, qs, name):
        return qs.filter(VERIFIED_FINDINGS_QUERY)

    def out_of_scope(self, qs, name):
        return qs.filter(OUT_OF_SCOPE_FINDINGS_QUERY)

    def false_positive(self, qs, name):
        return qs.filter(FALSE_POSITIVE_FINDINGS_QUERY)

    def inactive(self, qs, name):
        return qs.filter(INACTIVE_FINDINGS_QUERY)

    def risk_accepted(self, qs, name):
        return qs.filter(ACCEPTED_FINDINGS_QUERY)

    def closed(self, qs, name):
        return qs.filter(CLOSED_FINDINGS_QUERY)

    options = {
        '': (_('Any'), any),
        0: (_('Open'), open),
        1: (_('Verified'), verified),
        2: (_('Out Of Scope'), out_of_scope),
        3: (_('False Positive'), false_positive),
        4: (_('Inactive'), inactive),
        5: (_('Risk Accepted'), risk_accepted),
        6: (_('Closed'), closed),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(FindingStatusFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        earliest_finding = get_earliest_finding(qs)
        if earliest_finding is not None:
            start_date = local_tz.localize(datetime.combine(
                earliest_finding.date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](self, qs, self.field_name)


def get_earliest_finding(queryset=None):
    if queryset is None:  # don't to 'if not queryset' which will trigger the query
        queryset = Finding.objects.all()

    try:
        EARLIEST_FINDING = queryset.earliest('date')
    except (Finding.DoesNotExist, Endpoint_Status.DoesNotExist):
        EARLIEST_FINDING = None
    return EARLIEST_FINDING


def cwe_options(queryset):
    cwe = dict()
    cwe = dict([cwe, cwe]
                for cwe in queryset.order_by().values_list('cwe', flat=True).distinct()
                if type(cwe) is int and cwe is not None and cwe > 0)
    cwe = collections.OrderedDict(sorted(cwe.items()))
    return list(cwe.items())


class DojoFilter(FilterSet):
    def __init__(self, *args, **kwargs):
        super(DojoFilter, self).__init__(*args, **kwargs)

        for field in ['tags', 'test__tags', 'test__engagement__tags', 'test__engagement__product__tags',
                        'not_tags', 'not_test__tags', 'not_test__engagement__tags', 'not_test__engagement__product__tags']:
            if field in self.form.fields:
                tags_filter = self.filters['tags']
                model = tags_filter.model

                self.form.fields[field] = model._meta.get_field("tags").formfield()
                # we defer applying the select2 autocomplete because there can be multiple forms on the same page
                # and form.js would then apply select2 multiple times, resulting in duplicated fields
                # the initialization now happens in filter_js_snippet.html
                self.form.fields[field].widget.tag_options = \
                    self.form.fields[field].widget.tag_options + tagulous.models.options.TagOptions(autocomplete_settings={'width': '200px', 'defer': True})
                tagged_model, exclude = get_tags_model_from_field_name(field)
                if tagged_model:  # only if not the normal tags field
                    self.form.fields[field].label = get_tags_label_from_model(tagged_model)
                    self.form.fields[field].autocomplete_tags = tagged_model.tags.tag_model.objects.all().order_by('name')

                if exclude:
                    self.form.fields[field].label = 'Not ' + self.form.fields[field].label


def get_tags_model_from_field_name(field):
    exclude = False
    if field.startswith('not_'):
        field = field.replace('not_', '')
        exclude = True
    try:
        parts = field.split('__')
        model_name = parts[-2]
        return apps.get_model('dojo.%s' % model_name, require_ready=True), exclude
    except Exception as e:
        return None, exclude


def get_tags_label_from_model(model):
    if model:
        return 'Tags (%s)' % model.__name__.title()
    else:
        return 'Tags (Unknown)'


def get_finding_filter_fields(metrics=False, similar=False):
    fields = []

    if similar:
        fields.extend([
            'id',
            'unique_id_from_tool',
            'vuln_id_from_tool',
            'hash_code'
        ])

    fields.extend(['title', 'component_name', 'component_version'])

    if metrics:
        fields.extend([
            'start_date',
            'end_date',
        ])

    fields.extend([
                'date',
                'cve',
                'cwe',
                'severity',
                'last_reviewed',
                'last_status_update',
                'mitigated',
                'reporter',
                'test__engagement__product__prod_type',
                'test__engagement__product',
                'test__engagement',
                'test',
                'test__test_type',
                'test__engagement__version',
                'test__version',
                'status',
                'active',
                'verified',
                'duplicate',
                'is_mitigated',
                'out_of_scope',
                'false_p',
                'risk_accepted',
                'has_component',
                'has_notes',
                'file_path',
    ])

    if similar:
        fields.extend([
            'id',
        ])

    fields.extend([
                'sourcefilepath',
                'param',
                'payload',
                'risk_acceptance',
    ])

    if get_system_setting('enable_jira'):
        fields.extend([
            'has_jira_issue',
            'jira_creation',
            'jira_change',
            'jira_issue__jira_key',
        ])

    if settings.FEATURE_FINDING_GROUPS:
        fields.extend([
            'has_finding_group',
            'finding_group',
        ])

        if get_system_setting('enable_jira'):
            fields.extend([
                'has_jira_group_issue',
            ])

    return fields


class FindingFilterWithTags(DojoFilter):
    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name='test__tags__name',
        to_field_name='name',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__tags__name',
        to_field_name='name',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__product__tags__name',
        to_field_name='name',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__tags = ModelMultipleChoiceFilter(
        field_name='test__tags__name',
        to_field_name='name',
        exclude=True,
        label='Test without tags',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__tags__name',
        to_field_name='name',
        exclude=True,
        label='Engagement without tags',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__product__tags__name',
        to_field_name='name',
        exclude=True,
        label='Product without tags',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DateRangeFilter(ChoiceFilter):
    options = {
        '': (_('Any date'), lambda qs, name: qs.all()),
        1: (_('Today'), lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month,
            '%s__day' % name: now().day
        })),
        2: (_('Past 7 days'), lambda qs, name: qs.filter(**{
            '%s__gte' % name: _truncate(now() - timedelta(days=7)),
            '%s__lt' % name: _truncate(now() + timedelta(days=1)),
        })),
        3: (_('Past 30 days'), lambda qs, name: qs.filter(**{
            '%s__gte' % name: _truncate(now() - timedelta(days=30)),
            '%s__lt' % name: _truncate(now() + timedelta(days=1)),
        })),
        4: (_('Past 90 days'), lambda qs, name: qs.filter(**{
            '%s__gte' % name: _truncate(now() - timedelta(days=90)),
            '%s__lt' % name: _truncate(now() + timedelta(days=1)),
        })),
        5: (_('Current month'), lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month
        })),
        6: (_('Current year'), lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
        })),
        7: (_('Past year'), lambda qs, name: qs.filter(**{
            '%s__gte' % name: _truncate(now() - timedelta(days=365)),
            '%s__lt' % name: _truncate(now() + timedelta(days=1)),
        })),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(DateRangeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](qs, self.field_name)


class ReportBooleanFilter(ChoiceFilter):
    options = {
        '': (_('Either'), lambda qs, name: qs.all()),
        1: (_('Yes'), lambda qs, name: qs.filter(**{
            '%s' % name: True
        })),
        2: (_('No'), lambda qs, name: qs.filter(**{
            '%s' % name: False
        })),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(ReportBooleanFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](qs, self.field_name)


class ReportRiskAcceptanceFilter(ChoiceFilter):

    def any(self, qs, name):
        return qs.all()

    def accepted(self, qs, name):
        # return qs.filter(risk_acceptance__isnull=False)
        from dojo.finding.views import ACCEPTED_FINDINGS_QUERY
        return qs.filter(ACCEPTED_FINDINGS_QUERY)

    def not_accepted(self, qs, name):
        from dojo.finding.views import NOT_ACCEPTED_FINDINGS_QUERY
        return qs.filter(NOT_ACCEPTED_FINDINGS_QUERY)

    def was_accepted(self, qs, name):
        from dojo.finding.views import WAS_ACCEPTED_FINDINGS_QUERY
        return qs.filter(WAS_ACCEPTED_FINDINGS_QUERY)

    options = {
        '': (_('Either'), any),
        1: (_('Yes'), accepted),
        2: (_('No'), not_accepted),
        3: (_('Was'), was_accepted),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(ReportRiskAcceptanceFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](self, qs, self.field_name)


class MetricsDateRangeFilter(ChoiceFilter):
    def any(self, qs, name):
        earliest_finding = get_earliest_finding(qs)
        if earliest_finding is not None:
            start_date = local_tz.localize(datetime.combine(
                earliest_finding.date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
            return qs.all()

    def current_month(self, qs, name):
        self.start_date = local_tz.localize(
            datetime(now().year, now().month, 1, 0, 0, 0))
        self.end_date = now()
        return qs.filter(**{
            '%s__year' % name: self.start_date.year,
            '%s__month' % name: self.start_date.month
        })

    def current_year(self, qs, name):
        self.start_date = local_tz.localize(
            datetime(now().year, 1, 1, 0, 0, 0))
        self.end_date = now()
        return qs.filter(**{
            '%s__year' % name: now().year,
        })

    def past_x_days(self, qs, name, days):
        self.start_date = _truncate(now() - timedelta(days=days))
        self.end_date = _truncate(now() + timedelta(days=1))
        return qs.filter(**{
            '%s__gte' % name: self.start_date,
            '%s__lt' % name: self.end_date,
        })

    def past_seven_days(self, qs, name):
        return self.past_x_days(qs, name, 7)

    def past_thirty_days(self, qs, name):
        return self.past_x_days(qs, name, 30)

    def past_ninety_days(self, qs, name):
        return self.past_x_days(qs, name, 90)

    def past_six_months(self, qs, name):
        return self.past_x_days(qs, name, 183)

    def past_year(self, qs, name):
        return self.past_x_days(qs, name, 365)

    options = {
        '': (_('Past 30 days'), past_thirty_days),
        1: (_('Past 7 days'), past_seven_days),
        2: (_('Past 90 days'), past_ninety_days),
        3: (_('Current month'), current_month),
        4: (_('Current year'), current_year),
        5: (_('Past 6 Months'), past_six_months),
        6: (_('Past year'), past_year),
        7: (_('Any date'), any),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(MetricsDateRangeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        if value == 8:
            return qs
        earliest_finding = get_earliest_finding(qs)
        if earliest_finding is not None:
            start_date = local_tz.localize(datetime.combine(
                earliest_finding.date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](self, qs, self.field_name)


class ProductComponentFilter(DojoFilter):
    component_name = CharFilter(lookup_expr='icontains', label="Module Name")
    component_version = CharFilter(lookup_expr='icontains', label="Module Version")

    o = OrderingFilter(
        fields=(
            ('component_name', 'component_name'),
            ('component_version', 'component_version'),
            ('active', 'active'),
            ('duplicate', 'duplicate'),
            ('total', 'total'),
        ),
        field_labels={
            'component_name': 'Component Name',
            'component_version': 'Component Version',
            'active': 'Active',
            'duplicate': 'Duplicate',
            'total': 'Total',
        }
    )


class ComponentFilter(ProductComponentFilter):
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.none(),
        label="Product")

    def __init__(self, *args, **kwargs):
        super(ComponentFilter, self).__init__(*args, **kwargs)
        self.form.fields[
            'test__engagement__product__prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)
        self.form.fields[
            'test__engagement__product'].queryset = get_authorized_products(Permissions.Product_View)


class EngagementDirectFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains', label='Engagement name contains')
    lead = ModelChoiceFilter(
        queryset=Dojo_User.objects.filter(
            engagement__lead__isnull=False).distinct(),
        label="Lead")
    version = CharFilter(field_name='version', lookup_expr='icontains', label='Engagement version')
    test__version = CharFilter(field_name='test__version', lookup_expr='icontains', label='Test version')

    product__name = CharFilter(lookup_expr='icontains', label='Product name contains')
    product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")
    status = MultipleChoiceFilter(choices=ENGAGEMENT_STATUS_CHOICES,
                                              label="Status")

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
            ('product__name', 'product__name'),
            ('product__prod_type__name', 'product__prod_type__name'),
            ('lead__first_name', 'lead__first_name'),
        ),
        field_labels={
            'name': 'Engagement',
            'product__name': 'Product Name',
            'product__prod_type__name': 'Product Type',
            'lead__first_name': 'Lead',
        }

    )

    def __init__(self, *args, **kwargs):
        super(EngagementDirectFilter, self).__init__(*args, **kwargs)
        self.form.fields['product__prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)

    class Meta:
        model = Engagement
        fields = ['product__name', 'product__prod_type']


class EngagementFilter(DojoFilter):
    engagement__name = CharFilter(lookup_expr='icontains', label='Engagement name contains')
    engagement__lead = ModelChoiceFilter(
        queryset=Dojo_User.objects.filter(
            engagement__lead__isnull=False).distinct(),
        label="Lead")
    engagement__version = CharFilter(field_name='engagement__version', lookup_expr='icontains', label='Engagement version')
    engagement__test__version = CharFilter(field_name='engagement__test__version', lookup_expr='icontains', label='Test version')

    name = CharFilter(lookup_expr='icontains', label='Product name contains')
    prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")
    engagement__status = MultipleChoiceFilter(choices=ENGAGEMENT_STATUS_CHOICES,
                                              label="Status")

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
            ('prod_type__name', 'prod_type__name'),
        ),
        field_labels={
            'name': 'Product Name',
            'prod_type__name': 'Product Type',
        }

    )

    def __init__(self, *args, **kwargs):
        super(EngagementFilter, self).__init__(*args, **kwargs)
        self.form.fields['prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)

    class Meta:
        model = Product
        fields = ['name', 'prod_type']


class ProductEngagementFilter(DojoFilter):
    lead = ModelChoiceFilter(
        queryset=Dojo_User.objects.filter(
            engagement__lead__isnull=False).distinct(),
        label="Lead")
    version = CharFilter(lookup_expr='icontains', label='Engagement version')
    test__version = CharFilter(field_name='test__version', lookup_expr='icontains', label='Test version')

    name = CharFilter(lookup_expr='icontains')
    status = MultipleChoiceFilter(choices=ENGAGEMENT_STATUS_CHOICES,
                                              label="Status")

    target_start = DateRangeFilter()
    target_end = DateRangeFilter()

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
            ('version', 'version'),
            ('target_start', 'target_start'),
            ('target_end', 'target_end'),
            ('status', 'status'),
            ('lead', 'lead'),
        ),
        field_labels={
            'name': 'Engagement Name',
        }

    )

    class Meta:
        model = Product
        fields = ['id', 'name']


class ApiEngagementFilter(DojoFilter):
    product__prod_type = NumberInFilter(field_name='product__prod_type', lookup_expr='in')
    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')
    product__tags__name = CharFieldInFilter(field_name='product__tags__name',
                                            lookup_expr='in',
                                            help_text='Comma seperated list of exact tags present on product')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on model', exclude='True')
    not_product__tags__name = CharFieldInFilter(field_name='product__tags__name',
                                                lookup_expr='in',
                                                help_text='Comma seperated list of exact tags not present on product',
                                                exclude='True')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
            ('version', 'version'),
            ('target_start', 'target_start'),
            ('target_end', 'target_end'),
            ('status', 'status'),
            ('lead', 'lead'),
            ('created', 'created'),
            ('updated', 'updated'),
        ),
        field_labels={
            'name': 'Engagement Name',
        }

    )

    class Meta:
        model = Engagement
        fields = ['id', 'active', 'target_start',
                     'target_end', 'requester', 'report_type',
                     'updated', 'threat_model', 'api_test',
                     'pen_test', 'status', 'product', 'name', 'version', 'tags']


class ProductFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains', label="Product Name")
    prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")
    business_criticality = MultipleChoiceFilter(choices=Product.BUSINESS_CRITICALITY_CHOICES)
    platform = MultipleChoiceFilter(choices=Product.PLATFORM_CHOICES)
    lifecycle = MultipleChoiceFilter(choices=Product.LIFECYCLE_CHOICES)
    origin = MultipleChoiceFilter(choices=Product.ORIGIN_CHOICES)
    external_audience = BooleanFilter(field_name='external_audience')
    internet_accessible = BooleanFilter(field_name='internet_accessible')

    # not specifying anything for tags will render a multiselect input functioning as OR

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    # tags_and = ModelMultipleChoiceFilter(
    #     field_name='tags__name',
    #     to_field_name='name',
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label='tags (AND)',
    #     conjoined=True,
    # )

    # tags__name = ModelMultipleChoiceFilter(
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label="tags (AND)"
    # )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label="Tag contains")

    # tags__name = CharFilter(
    #     lookup_expr='icontains',
    #     label="Tag contains",
    # )

    # tags__all = ModelMultipleChoiceFilter(
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     field_name='tags__name',
    #     label="tags (AND)"
    # )

    # not working below

    # tags = ModelMultipleChoiceFilter(
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label="tags_widget", widget=TagWidget, tag_options=tagulous.models.TagOptions(
    #         force_lowercase=True,)
    # ,)

    # tags__name = CharFilter(lookup_expr='icontains')

    # tags__and = ModelMultipleChoiceFilter(
    #     field_name='tags__name',
    #     to_field_name='name',
    #     lookup_expr='in',
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label="tags (AND)"
    # )

    # tags = ModelMultipleChoiceFilter(
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label="tags (OR)"
    # )

    # tags = ModelMultipleChoiceFilter(
    #     field_name='tags__name',
    #     to_field_name='name',
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label="tags (OR2)",
    # )

    # tags = ModelMultipleChoiceFilter(
    #     field_name='tags',
    #     to_field_name='name',
    #     # lookup_expr='icontains', # nor working
    #     # without lookup_expr we get an error: ValueError: invalid literal for int() with base 10: 'magento'
    #     queryset=Product.tags.tag_model.objects.all().order_by('name'),
    #     label="tags (OR3)",
    # )

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
            ('prod_type__name', 'prod_type__name'),
            ('business_criticality', 'business_criticality'),
            ('platform', 'platform'),
            ('lifecycle', 'lifecycle'),
            ('origin', 'origin'),
            ('external_audience', 'external_audience'),
            ('internet_accessible', 'internet_accessible'),
        ),
        field_labels={
            'name': 'Product Name',
            'prod_type__name': 'Product Type',
            'business_criticality': 'Business Criticality',
            'platform': 'Platform ',
            'lifecycle': 'Lifecycle ',
            'origin': 'Origin ',
            'external_audience': 'External Audience ',
            'internet_accessible': 'Internet Accessible ',
        }

    )

    # tags = CharFilter(lookup_expr='icontains', label="Tags")

    def __init__(self, *args, **kwargs):
        self.user = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')

        super(ProductFilter, self).__init__(*args, **kwargs)

        self.form.fields['prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)

    class Meta:
        model = Product
        fields = ['name', 'prod_type', 'business_criticality', 'platform', 'lifecycle', 'origin', 'external_audience',
                  'internet_accessible', 'tags']


class ApiProductFilter(DojoFilter):
    # BooleanFilter
    external_audience = BooleanFilter(field_name='external_audience')
    internet_accessible = BooleanFilter(field_name='internet_accessible')
    # CharFilter
    name = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')
    business_criticality = CharFilter(method=custom_filter, field_name='business_criticality')
    platform = CharFilter(method=custom_filter, field_name='platform')
    lifecycle = CharFilter(method=custom_filter, field_name='lifecycle')
    origin = CharFilter(method=custom_filter, field_name='origin')
    # NumberInFilter
    id = NumberInFilter(field_name='id', lookup_expr='in')
    product_manager = NumberInFilter(field_name='product_manager', lookup_expr='in')
    technical_contact = NumberInFilter(field_name='technical_contact', lookup_expr='in')
    team_manager = NumberInFilter(field_name='team_manager', lookup_expr='in')
    prod_type = NumberInFilter(field_name='prod_type', lookup_expr='in')
    tid = NumberInFilter(field_name='tid', lookup_expr='in')
    authorized_users = NumberInFilter(field_name='authorized_users', lookup_expr='in')
    prod_numeric_grade = NumberInFilter(field_name='prod_numeric_grade', lookup_expr='in')
    user_records = NumberInFilter(field_name='user_records', lookup_expr='in')
    regulations = NumberInFilter(field_name='regulations', lookup_expr='in')

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on product', exclude='True')

    # DateRangeFilter
    created = DateRangeFilter()
    updated = DateRangeFilter()
    # NumberFilter
    revenue = NumberFilter()

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('id', 'id'),
            ('tid', 'tid'),
            ('name', 'name'),
            ('created', 'created'),
            ('prod_numeric_grade', 'prod_numeric_grade'),
            ('business_criticality', 'business_criticality'),
            ('platform', 'platform'),
            ('lifecycle', 'lifecycle'),
            ('origin', 'origin'),
            ('revenue', 'revenue'),
            ('external_audience', 'external_audience'),
            ('internet_accessible', 'internet_accessible'),
            ('product_manager', 'product_manager'),
            ('product_manager__first_name', 'product_manager__first_name'),
            ('product_manager__last_name', 'product_manager__last_name'),
            ('technical_contact', 'technical_contact'),
            ('technical_contact__first_name', 'technical_contact__first_name'),
            ('technical_contact__last_name', 'technical_contact__last_name'),
            ('team_manager', 'team_manager'),
            ('team_manager__first_name', 'team_manager__first_name'),
            ('team_manager__last_name', 'team_manager__last_name'),
            ('prod_type', 'prod_type'),
            ('prod_type__name', 'prod_type__name'),
            ('updated', 'updated'),
            ('user_records', 'user_records')
        )
    )


class ApiFindingFilter(DojoFilter):
    # BooleanFilter
    active = BooleanFilter(field_name='active')
    duplicate = BooleanFilter(field_name='duplicate')
    dynamic_finding = BooleanFilter(field_name='dynamic_finding')
    false_p = BooleanFilter(field_name='false_p')
    is_mitigated = BooleanFilter(field_name='is_mitigated')
    out_of_scope = BooleanFilter(field_name='out_of_scope')
    static_finding = BooleanFilter(field_name='static_finding')
    under_defect_review = BooleanFilter(field_name='under_defect_review')
    under_review = BooleanFilter(field_name='under_review')
    verified = BooleanFilter(field_name='verified')
    # CharFilter
    component_version = CharFilter(lookup_expr='icontains')
    component_name = CharFilter(lookup_expr='icontains')
    cve = CharFilter(method=custom_filter, field_name='cve')
    description = CharFilter(lookup_expr='icontains')
    file_path = CharFilter(lookup_expr='icontains')
    hash_code = CharFilter(lookup_expr='icontains')
    impact = CharFilter(lookup_expr='icontains')
    mitigation = CharFilter(lookup_expr='icontains')
    numerical_severity = CharFilter(method=custom_filter, field_name='numerical_severity')
    param = CharFilter(lookup_expr='icontains')
    payload = CharFilter(lookup_expr='icontains')
    references = CharFilter(lookup_expr='icontains')
    severity = CharFilter(method=custom_filter, field_name='severity')
    severity_justification = CharFilter(lookup_expr='icontains')
    step_to_reproduce = CharFilter(lookup_expr='icontains')
    sourcefile = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr='icontains')
    unique_id_from_tool = CharFilter(lookup_expr='icontains')
    title = CharFilter(lookup_expr='icontains')
    # DateRangeFilter
    created = DateRangeFilter()
    date = DateRangeFilter()
    jira_creation = DateRangeFilter(field_name='jira_issue__jira_creation')
    jira_change = DateRangeFilter(field_name='jira_issue__jira_change')
    last_reviewed = DateRangeFilter()
    mitigated = DateRangeFilter()
    # NumberInFilter
    cwe = NumberInFilter(field_name='cwe', lookup_expr='in')
    defect_review_requested_by = NumberInFilter(field_name='defect_review_requested_by', lookup_expr='in')
    endpoints = NumberInFilter(field_name='endpoints', lookup_expr='in')
    found_by = NumberInFilter(field_name='found_by', lookup_expr='in')
    id = NumberInFilter(field_name='id', lookup_expr='in')
    last_reviewed_by = NumberInFilter(field_name='last_reviewed_by', lookup_expr='in')
    mitigated_by = NumberInFilter(field_name='mitigated_by', lookup_expr='in')
    nb_occurences = NumberInFilter(field_name='nb_occurences', lookup_expr='in')
    reporter = NumberInFilter(field_name='reporter', lookup_expr='in')
    scanner_confidence = NumberInFilter(field_name='scanner_confidence', lookup_expr='in')
    review_requested_by = NumberInFilter(field_name='review_requested_by', lookup_expr='in')
    reviewers = NumberInFilter(field_name='reviewers', lookup_expr='in')
    sast_source_line = NumberInFilter(field_name='sast_source_line', lookup_expr='in')
    sonarqube_issue = NumberInFilter(field_name='sonarqube_issue', lookup_expr='in')
    test__test_type = NumberInFilter(field_name='test__test_type', lookup_expr='in', label='Test Type')
    test__engagement = NumberInFilter(field_name='test__engagement', lookup_expr='in')
    test__engagement__product = NumberInFilter(field_name='test__engagement__product', lookup_expr='in')
    finding_group = NumberInFilter(field_name='finding_group', lookup_expr='in')

    # ReportRiskAcceptanceFilter
    risk_acceptance = ReportRiskAcceptanceFilter()

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')
    test__tags = CharFieldInFilter(field_name='test__tags__name', lookup_expr='in',
                                   help_text='Comma seperated list of exact tags present on test')
    test__engagement__tags = CharFieldInFilter(field_name='test__engagement__tags', lookup_expr='in',
                                               help_text='Comma seperated list of exact tags present on engagement')
    test__engagement__product__tags__name = CharFieldInFilter(field_name='test__engagement__product__tags__name',
                                                              lookup_expr='in',
                                                              help_text='Comma seperated list of exact tags present on product')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on model', exclude='True')
    not_test__tags = CharFieldInFilter(field_name='test__tags__name', lookup_expr='in',
                                       help_text='Comma seperated list of exact tags not present on test', exclude='True')
    not_test__engagement__tags = CharFieldInFilter(field_name='test__engagement__tags', lookup_expr='in',
                                                   help_text='Comma seperated list of exact tags not present on engagement',
                                                   exclude='True')
    not_test__engagement__product__tags__name = CharFieldInFilter(field_name='test__engagement__product__tags__name',
                                                                  lookup_expr='in',
                                                                  help_text='Comma seperated list of exact tags not present on product',
                                                                  exclude='True')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('active', 'active'),
            ('component_name', 'component_name'),
            ('component_version', 'component_version'),
            ('created', 'created'),
            ('last_status_update', 'last_status_update'),
            ('last_reviewed', 'last_reviewed'),
            ('cve', 'cve'),
            ('cwe', 'cwe'),
            ('date', 'date'),
            ('duplicate', 'duplicate'),
            ('dynamic_finding', 'dynamic_finding'),
            ('false_p', 'false_p'),
            ('found_by', 'found_by'),
            ('id', 'id'),
            ('is_mitigated', 'is_mitigated'),
            ('numerical_severity', 'numerical_severity'),
            ('out_of_scope', 'out_of_scope'),
            ('severity', 'severity'),
            ('reviewers', 'reviewers'),
            ('static_finding', 'static_finding'),
            ('test__engagement__product__name', 'test__engagement__product__name'),
            ('title', 'title'),
            ('under_defect_review', 'under_defect_review'),
            ('under_review', 'under_review'),
            ('verified', 'verified'),
        ),
    )

    class Meta:
        model = Finding
        exclude = ['url', 'is_template', 'thread_id', 'notes', 'files',
                   'sourcefile', 'line', 'endpoint_status']


class FindingFilter(FindingFilterWithTags):
    # tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    title = CharFilter(lookup_expr='icontains')
    date = DateRangeFilter()
    last_reviewed = DateRangeFilter()
    last_status_update = DateRangeFilter()
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(
        queryset=Test_Type.objects.all(), label='Test Type')

    duplicate = ReportBooleanFilter()
    is_mitigated = ReportBooleanFilter()
    mitigated = DateRangeFilter(label="Mitigated Date")

    # sourcefile = CharFilter(lookup_expr='icontains')
    file_path = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr='icontains')
    param = CharFilter(lookup_expr='icontains')
    payload = CharFilter(lookup_expr='icontains')

    reporter = ModelMultipleChoiceFilter(
        queryset=Dojo_User.objects.all())
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")

    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.none(),
        label="Product")
    test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.none(),
        label="Engagement")

    test = ModelMultipleChoiceFilter(
        queryset=Test.objects.none(),
        label="Test")

    test__engagement__version = CharFilter(lookup_expr='icontains', label="Engagement Version")
    test__version = CharFilter(lookup_expr='icontains', label="Test Version")

    status = FindingStatusFilter(label='Status')

    if settings.FEATURE_FINDING_GROUPS:
        finding_group = ModelMultipleChoiceFilter(
            queryset=Finding_Group.objects.none(),
            label="Finding Group")

        has_finding_group = BooleanFilter(field_name='finding_group',
                                    lookup_expr='isnull',
                                    exclude=True,
                                    label='Is Grouped')

    risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted")

    test_import_finding_action__test_import = NumberFilter(widget=HiddenInput())

    if get_system_setting('enable_jira'):
        has_jira_issue = BooleanFilter(field_name='jira_issue',
                                    lookup_expr='isnull',
                                    exclude=True,
                                    label='Has JIRA')
        jira_creation = DateRangeFilter(field_name='jira_issue__jira_creation', label='JIRA Creation')
        jira_change = DateRangeFilter(field_name='jira_issue__jira_change', label='JIRA Updated')
        jira_issue__jira_key = CharFilter(field_name='jira_issue__jira_key', lookup_expr='icontains', label="JIRA issue")

        if settings.FEATURE_FINDING_GROUPS:
            has_jira_group_issue = BooleanFilter(field_name='finding_group__jira_issue',
                                        lookup_expr='isnull',
                                        exclude=True,
                                        label='Has Group JIRA')

    has_component = BooleanFilter(field_name='component_name',
                                lookup_expr='isnull',
                                exclude=True,
                                label='Has Component')

    has_notes = BooleanFilter(field_name='notes',
                                lookup_expr='isnull',
                                exclude=True,
                                label='Has notes')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__tags = ModelMultipleChoiceFilter(
        field_name='test__tags__name',
        to_field_name='name',
        exclude=True,
        label='Test without tags',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__tags__name',
        to_field_name='name',
        exclude=True,
        label='Engagement without tags',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__product__tags__name',
        to_field_name='name',
        exclude=True,
        label='Product without tags',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('numerical_severity', 'numerical_severity'),
            ('date', 'date'),
            ('mitigated', 'mitigated'),
            ('risk_acceptance__created__date',
             'risk_acceptance__created__date'),
            ('last_reviewed', 'last_reviewed'),
            ('title', 'title'),
            ('test__engagement__product__name',
             'test__engagement__product__name'),
        ),
        field_labels={
            'numerical_severity': 'Severity',
            'date': 'Date',
            'risk_acceptance__created__date': 'Acceptance Date',
            'mitigated': 'Mitigated Date',
            'title': 'Finding Name',
            'test__engagement__product__name': 'Product Name',
        }
    )

    class Meta:
        model = Finding
        fields = get_finding_filter_fields()

        exclude = ['url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'is_template',
                   'thread_id', 'notes', 'scanner_confidence',
                   'numerical_severity', 'line', 'duplicate_finding',
                   'hash_code', 'endpoint_status',
                   'line_number', 'reviewers', 'sourcefile',
                   'created', 'files', 'sla_start_date', 'cvssv3',
                   'severity_justification', 'steps_to_reproduce']

    def __init__(self, *args, **kwargs):
        self.user = None
        self.pid = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')

        if 'pid' in kwargs:
            self.pid = kwargs.pop('pid')
        super().__init__(*args, **kwargs)

        self.form.fields['cwe'].choices = cwe_options(self.queryset)

        # Don't show the product filter on the product finding view
        if self.pid:
            del self.form.fields['test__engagement__product']
            del self.form.fields['test__engagement__product__prod_type']
            # TODO add authorized check to be sure
            self.form.fields['test__engagement'].queryset = Engagement.objects.filter(
                product_id=self.pid
            ).all()
            self.form.fields['test'].queryset = get_authorized_tests(Permissions.Test_View, product=self.pid).prefetch_related('test_type')
        else:
            self.form.fields[
                'test__engagement__product__prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)
            self.form.fields['test__engagement'].queryset = get_authorized_engagements(Permissions.Engagement_View)
            del self.form.fields['test']

        if self.form.fields.get('test__engagement__product'):
            self.form.fields['test__engagement__product'].queryset = get_authorized_products(Permissions.Product_View)
        if self.form.fields.get('finding_group', None):
            self.form.fields['finding_group'].queryset = get_authorized_finding_groups(Permissions.Finding_Group_View)
        if self.form.fields.get('endpoints'):
            self.form.fields['endpoints'].queryset = get_authorized_endpoints(Permissions.Endpoint_View).distinct()


class OpenFindingFilter(FindingFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ClosedFindingFilter(FindingFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AcceptedFindingFilter(FindingFilter):
    risk_acceptance__created__date = \
        DateRangeFilter(label="Acceptance Date")

    risk_acceptance__owner = \
        ModelMultipleChoiceFilter(
            queryset=Dojo_User.objects.all(),
            label="Risk Acceptance Owner")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SimilarFindingFilter(FindingFilter):
    hash_code = MultipleChoiceFilter()

    class Meta(FindingFilter.Meta):
        model = Finding
        # slightly different fields from FindingFilter, but keep the same ordering for UI consistency
        fields = get_finding_filter_fields(similar=True)

    def __init__(self, data=None, *args, **kwargs):
        self.user = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')

        self.finding = None
        if 'finding' in kwargs:
            self.finding = kwargs.pop('finding')

        # if filterset is bound, use initial values as defaults
        # because of this, we can't rely on the self.form.has_changed
        self.has_changed = True
        if not data and self.finding:
            # get a mutable copy of the QueryDict
            data = data.copy()

            data['cve'] = self.finding.cve
            data['cwe'] = self.finding.cwe
            data['file_path'] = self.finding.file_path
            data['line'] = self.finding.line
            data['unique_id_from_tool'] = self.finding.unique_id_from_tool
            data['test__test_type'] = self.finding.test.test_type
            data['test__engagement__product'] = self.finding.test.engagement.product
            data['test__engagement__product__prod_type'] = self.finding.test.engagement.product.prod_type

            self.has_changed = False

        super().__init__(data, *args, **kwargs)

        if self.finding and self.finding.hash_code:
            self.form.fields['hash_code'] = forms.MultipleChoiceField(choices=[(self.finding.hash_code, self.finding.hash_code[:24] + '...')], required=False, initial=[])

    def filter_queryset(self, *args, **kwargs):
        queryset = super().filter_queryset(*args, **kwargs)
        queryset = get_authorized_findings(Permissions.Finding_View, queryset, self.user)
        queryset = queryset.exclude(pk=self.finding.pk)
        return queryset


class TemplateFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains')
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('cwe', 'cwe'),
            ('title', 'title'),
            ('numerical_severity', 'numerical_severity'),
        ),
        field_labels={
            'numerical_severity': 'Severity',
        }
    )

    class Meta:
        model = Finding_Template
        exclude = ['description', 'mitigation', 'impact',
                   'references', 'numerical_severity']

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__tags = ModelMultipleChoiceFilter(
        field_name='test__tags__name',
        to_field_name='name',
        exclude=True,
        label='Test without tags',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__tags__name',
        to_field_name='name',
        exclude=True,
        label='Engagement without tags',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__product__tags__name',
        to_field_name='name',
        exclude=True,
        label='Product without tags',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    def __init__(self, *args, **kwargs):
        super(TemplateFindingFilter, self).__init__(*args, **kwargs)
        self.form.fields['cwe'].choices = cwe_options(self.queryset)


class ApiTemplateFindingFilter(DojoFilter):
    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on model', exclude='True')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('title', 'title'),
            ('cwe', 'cwe'),
        ),
    )

    class Meta:
        model = Finding_Template
        fields = ['id', 'title', 'cwe', 'severity', 'description',
                     'mitigation']


class MetricsFindingFilter(FindingFilter):
    start_date = DateFilter(field_name='date', label='Start Date', lookup_expr=('gt'))
    end_date = DateFilter(field_name='date', label='End Date', lookup_expr=('lt'))
    date = MetricsDateRangeFilter()

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Endpoint.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    def __init__(self, *args, **kwargs):
        if args[0]:
            if args[0].get('start_date', '') != '' or args[0].get('end_date', '') != '':
                args[0]._mutable = True
                args[0]['date'] = 8
                args[0]._mutable = False

        super().__init__(*args, **kwargs)

    class Meta(FindingFilter.Meta):
        model = Finding
        fields = get_finding_filter_fields(metrics=True)


class MetricsEndpointFilter(FilterSet):
    start_date = DateFilter(field_name='date', label='Start Date', lookup_expr=('gt'))
    end_date = DateFilter(field_name='date', label='End Date', lookup_expr=('lt'))
    date = MetricsDateRangeFilter()
    finding__test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")
    finding__test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.none(),
        label="Engagement")
    finding__test__engagement__version = CharFilter(lookup_expr='icontains', label="Engagement Version")
    finding__severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES, label="Severity")

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Endpoint.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Endpoint.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__tags = ModelMultipleChoiceFilter(
        field_name='test__tags__name',
        to_field_name='name',
        exclude=True,
        label='Test without tags',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__tags__name',
        to_field_name='name',
        exclude=True,
        label='Engagement without tags',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__product__tags__name',
        to_field_name='name',
        exclude=True,
        label='Product without tags',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    def __init__(self, *args, **kwargs):
        if args[0]:
            if args[0].get('start_date', '') != '' or args[0].get('end_date', '') != '':
                args[0]._mutable = True
                args[0]['date'] = 8
                args[0]._mutable = False

        self.pid = None
        if 'pid' in kwargs:
            self.pid = kwargs.pop('pid')

        super().__init__(*args, **kwargs)
        if self.pid:
            del self.form.fields['finding__test__engagement__product__prod_type']
            self.form.fields['finding__test__engagement'].queryset = Engagement.objects.filter(
                product_id=self.pid
            ).all()
        else:
            self.form.fields['finding__test__engagement'].queryset = get_authorized_engagements(Permissions.Engagement_View).order_by('name')

        if 'finding__test__engagement__product__prod_type' in self.form.fields:
            self.form.fields[
                'finding__test__engagement__product__prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)

        self.form.fields['finding'].queryset = get_authorized_findings(Permissions.Finding_View)
        self.form.fields['endpoint'].queryset = get_authorized_endpoints(Permissions.Endpoint_View)

    class Meta:
        model = Endpoint_Status
        exclude = ['last_modified']


class EndpointFilter(DojoFilter):
    product = ModelMultipleChoiceFilter(
        queryset=Product.objects.none(),
        label="Product")
    protocol = CharFilter(lookup_expr='icontains')
    userinfo = CharFilter(lookup_expr='icontains')
    host = CharFilter(lookup_expr='icontains')
    port = NumberFilter()
    path = CharFilter(lookup_expr='icontains')
    query = CharFilter(lookup_expr='icontains')
    fragment = CharFilter(lookup_expr='icontains')
    mitigated = ReportBooleanFilter()

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Endpoint.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name='test__tags__name',
        to_field_name='name',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__tags__name',
        to_field_name='name',
        queryset=Engagement.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name='test__engagement__product__tags__name',
        to_field_name='name',
        queryset=Product.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Finding.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('product', 'product'),
            ('host', 'host'),
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')
        super(EndpointFilter, self).__init__(*args, **kwargs)
        self.form.fields['product'].queryset = get_authorized_products(Permissions.Product_View)

    @property
    def qs(self):
        parent = super(EndpointFilter, self).qs
        return get_authorized_endpoints(Permissions.Endpoint_View, parent)

    class Meta:
        model = Endpoint
        exclude = ['mitigated', 'endpoint_status']


class ApiEndpointFilter(DojoFilter):
    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on model', exclude='True')
    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('host', 'host'),
            ('product', 'product'),
        ),
    )

    class Meta:
        model = Endpoint
        fields = ['id', 'host', 'product']


class EngagementTestFilter(DojoFilter):
    lead = ModelChoiceFilter(
        queryset=Dojo_User.objects.filter(
            engagement__lead__isnull=False).distinct(),
        label="Lead")
    version = CharFilter(lookup_expr='icontains', label='Version')

    if settings.TRACK_IMPORT_HISTORY:
        test_import__version = CharFilter(field_name='test_import__version', lookup_expr='icontains', label='Reimported Version')

    target_start = DateRangeFilter()
    target_end = DateRangeFilter()

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Test.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('title', 'title'),
            ('version', 'version'),
            ('target_start', 'target_start'),
            ('target_end', 'target_end'),
            ('lead', 'lead'),
        ),
        field_labels={
            'name': 'Test Name',
        }

    )

    class Meta:
        model = Test
        fields = ['id', 'title', 'test_type', 'target_start',
                     'target_end', 'percent_complete',
                     'version']

    def __init__(self, *args, **kwargs):
        self.engagement = kwargs.pop('engagement')
        super(DojoFilter, self).__init__(*args, **kwargs)
        self.form.fields['test_type'].queryset = Test_Type.objects.filter(test__engagement=self.engagement).distinct().order_by('name')


class ApiTestFilter(DojoFilter):
    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')
    engagement__tags = CharFieldInFilter(field_name='engagement__tags', lookup_expr='in',
                                               help_text='Comma seperated list of exact tags present on engagement')
    engagement__product__tags__name = CharFieldInFilter(field_name='engagement__product__tags__name',
                                                              lookup_expr='in',
                                                              help_text='Comma seperated list of exact tags present on product')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on model', exclude='True')
    not_engagement__tags = CharFieldInFilter(field_name='engagement__tags', lookup_expr='in',
                                                   help_text='Comma seperated list of exact tags not present on engagement',
                                                   exclude='True')
    not_engagement__product__tags__name = CharFieldInFilter(field_name='engagement__product__tags__name',
                                                                  lookup_expr='in',
                                                                  help_text='Comma seperated list of exact tags not present on product',
                                                                  exclude='True')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('title', 'title'),
            ('version', 'version'),
            ('target_start', 'target_start'),
            ('target_end', 'target_end'),
            ('test_type', 'test_type'),
            ('lead', 'lead'),
            ('version', 'version'),
            ('branch_tag', 'branch_tag'),
            ('build_id', 'build_id'),
            ('commit_hash', 'commit_hash'),
            ('engagement', 'engagement'),
            ('created', 'created'),
            ('updated', 'updated'),
        ),
        field_labels={
            'name': 'Test Name',
        }
    )

    class Meta:
        model = Test
        fields = ['id', 'title', 'test_type', 'target_start',
                     'target_end', 'notes', 'percent_complete',
                     'actual_time', 'engagement', 'version',
                     'branch_tag', 'build_id', 'commit_hash']


class ApiAppAnalysisFilter(DojoFilter):
    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Tag name contains')
    tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                             help_text='Comma seperated list of exact tags')

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', help_text='Not Tag name contains', exclude='True')
    not_tags = CharFieldInFilter(field_name='tags__name', lookup_expr='in',
                                 help_text='Comma seperated list of exact tags not present on model', exclude='True')

    class Meta:
        model = App_Analysis
        fields = ['product', 'name', 'user', 'version']


class EndpointReportFilter(DojoFilter):
    protocol = CharFilter(lookup_expr='icontains')
    userinfo = CharFilter(lookup_expr='icontains')
    host = CharFilter(lookup_expr='icontains')
    port = NumberFilter()
    path = CharFilter(lookup_expr='icontains')
    query = CharFilter(lookup_expr='icontains')
    fragment = CharFilter(lookup_expr='icontains')
    finding__severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES, label='Severity')
    finding__mitigated = ReportBooleanFilter(label='Finding Mitigated')

    tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        queryset=Endpoint.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Tag name contains')

    not_tags = ModelMultipleChoiceFilter(
        field_name='tags__name',
        to_field_name='name',
        exclude=True,
        queryset=Endpoint.tags.tag_model.objects.all().order_by('name'),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    not_tag = CharFilter(field_name='tags__name', lookup_expr='icontains', label='Not tag name contains', exclude=True)

    class Meta:
        model = Endpoint
        exclude = ['product', 'endpoint_status']


class ReportFindingFilter(FindingFilterWithTags):
    title = CharFilter(lookup_expr='icontains', label='Name')
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.none(), label="Product")
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.none(),
        label="Product Type")
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    active = ReportBooleanFilter()
    is_mitigated = ReportBooleanFilter()
    mitigated = DateRangeFilter(label="Mitigated Date")
    verified = ReportBooleanFilter()
    false_p = ReportBooleanFilter(label="False Positive")
    risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted")
    # queryset will be restricted in __init__, here we don't have access to the logged in user
    duplicate = ReportBooleanFilter()
    duplicate_finding = ModelChoiceFilter(queryset=Finding.objects.filter(original_finding__isnull=False).distinct())
    out_of_scope = ReportBooleanFilter()

    file_path = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Finding
        # exclude sonarqube issue as by default it will show all without checking permissions
        exclude = ['date', 'cwe', 'url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template', 'sonarqube_issue'
                   'thread_id', 'notes', 'endpoints', 'endpoint_status',
                   'numerical_severity', 'reporter', 'last_reviewed',
                   'jira_creation', 'jira_change', 'files']

    def __init__(self, *args, **kwargs):
        self.prod_type = None
        self.product = None
        self.engagement = None
        self.test = None
        if 'prod_type' in kwargs:
            self.prod_type = kwargs.pop('prod_type')
        if 'product' in kwargs:
            self.product = kwargs.pop('product')
        if 'engagement' in kwargs:
            self.engagement = kwargs.pop('engagement')
        if 'test' in kwargs:
            self.test = kwargs.pop('test')

        super().__init__(*args, **kwargs)

        # duplicate_finding queryset needs to restricted in line with permissions
        # and inline with report scope to avoid a dropdown with 100K entries
        duplicate_finding_query_set = self.form.fields['duplicate_finding'].queryset
        duplicate_finding_query_set = get_authorized_findings(Permissions.Finding_View, duplicate_finding_query_set)

        if self.test:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(test=self.test)
            del self.form.fields['test__tags']
            del self.form.fields['test__engagement__tags']
            del self.form.fields['test__engagement__product__tags']
        if self.engagement:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(test__engagement=self.engagement)
            del self.form.fields['test__engagement__tags']
            del self.form.fields['test__engagement__product__tags']
        elif self.product:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(test__engagement__product=self.product)
            del self.form.fields['test__engagement__product']
            del self.form.fields['test__engagement__product__tags']
        elif self.prod_type:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(test__engagement__product__prod_type=self.prod_type)
            del self.form.fields['test__engagement__product__prod_type']

        self.form.fields['duplicate_finding'].queryset = duplicate_finding_query_set

        if 'test__engagement__product__prod_type' in self.form.fields:
            self.form.fields[
                'test__engagement__product__prod_type'].queryset = get_authorized_product_types(Permissions.Product_Type_View)
        if 'test__engagement__product' in self.form.fields:
            self.form.fields[
                'test__engagement__product'].queryset = get_authorized_products(Permissions.Product_View)

    @property
    def qs(self):
        parent = super().qs
        return get_authorized_findings(Permissions.Finding_View, parent)


class UserFilter(DojoFilter):
    first_name = CharFilter(lookup_expr='icontains')
    last_name = CharFilter(lookup_expr='icontains')
    username = CharFilter(lookup_expr='icontains')
    product_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(),
        label="Authorized Product Type")
    product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(),
        label="Authorized Product")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('username', 'username'),
            ('last_name', 'last_name'),
            ('first_name', 'first_name'),
            ('email', 'email'),
            ('is_active', 'is_active'),
            ('is_staff', 'is_staff'),
            ('is_superuser', 'is_superuser'),
        ),
        field_labels={
            'username': 'User Name',
            'is_active': 'Active',
            'is_staff': 'Staff',
            'is_superuser': 'Superuser',
        }

    )

    class Meta:
        model = Dojo_User
        fields = ['is_staff', 'is_superuser', 'is_active', 'first_name',
                  'last_name', 'username']
        exclude = ['password', 'last_login', 'groups', 'user_permissions',
                   'date_joined']


class GroupFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Dojo_Group
        fields = ['name', 'description']
        exclude = ['users']


class TestImportFilter(DojoFilter):
    version = CharFilter(field_name='version', lookup_expr='icontains')
    version_exact = CharFilter(field_name='version', lookup_expr='iexact', label='Version Exact')
    branch_tag = CharFilter(lookup_expr='icontains', label='Branch/Tag')
    build_id = CharFilter(lookup_expr='icontains', label="Build ID")
    commit_hash = CharFilter(lookup_expr='icontains', label="Commit hash")

    findings_affected = BooleanFilter(field_name='findings_affected', lookup_expr='isnull', exclude=True, label='Findings affected')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('date', 'date'),
            ('version', 'version'),
            ('branch_tag', 'branch_tag'),
            ('build_id', 'build_id'),
            ('commit_hash', 'commit_hash'),

        )
    )

    class Meta:
        model = Test_Import
        fields = []


class EngineerFilter(DojoFilter):
    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('username', 'username'),
            ('last_name', 'last_name'),
            ('first_name', 'first_name'),
            ('email', 'email'),
            ('is_active', 'is_active'),
            ('is_staff', 'is_staff'),
            ('is_superuser', 'is_superuser'),
        ),
        field_labels={
            'username': 'User Name',
            'is_active': 'Active',
            'is_staff': 'Staff',
            'is_superuser': 'Superuser',
        }

    )

    class Meta:
        model = Dojo_User
        fields = ['is_staff', 'is_superuser', 'is_active', 'username', 'email',
                  'last_name', 'first_name']
        exclude = ['password', 'last_login', 'groups', 'user_permissions',
                   'date_joined']


class LogEntryFilter(DojoFilter):
    from auditlog.models import LogEntry

    action = MultipleChoiceFilter(choices=LogEntry.Action.choices)
    actor = ModelMultipleChoiceFilter(queryset=Dojo_User.objects.all())
    timestamp = DateRangeFilter()

    class Meta:
        model = LogEntry
        exclude = ['content_type', 'object_pk', 'object_id', 'object_repr',
                   'changes', 'additional_data']


class ProductTypeFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
        ),
    )

    class Meta:
        model = Product_Type
        if settings.FEATURE_AUTHORIZATION_V2:
            exclude = ['authorized_users']
        else:
            exclude = ['members', 'authorization_groups']
        include = ('name',)


class TestTypeFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
        ),
    )

    class Meta:
        model = Test_Type
        exclude = []
        include = ('name',)


class DevelopmentEnvironmentFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
        ),
    )

    class Meta:
        model = Development_Environment
        exclude = []
        include = ('name',)


class NoteTypesFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('name', 'name'),
            ('description', 'description'),
            ('is_single', 'is_single'),
            ('is_mandatory', 'is_mandatory'),
        ),
    )

    class Meta:
        model = Note_Type
        exclude = []
        include = ('name', 'is_single', 'description')

# ==============================
# Defect Dojo Engaegment Surveys
# ==============================


class QuestionnaireFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')
    active = BooleanFilter()

    class Meta:
        model = Engagement_Survey
        exclude = ['questions']

    survey_set = FilterSet


class QuestionTypeFilter(ChoiceFilter):
    def any(self, qs, name):
        return qs.all()

    def text_question(self, qs, name):
        return qs.filter(polymorphic_ctype=ContentType.objects.get_for_model(TextQuestion))

    def choice_question(self, qs, name):
        return qs.filter(polymorphic_ctype=ContentType.objects.get_for_model(ChoiceQuestion))

    options = {
        '': (_('Any'), any),
        1: (_('Text Question'), text_question),
        2: (_('Choice Question'), choice_question),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(QuestionTypeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](self, qs, self.options[value][0])


class QuestionFilter(FilterSet):
    text = CharFilter(lookup_expr='icontains')
    type = QuestionTypeFilter()

    class Meta:
        model = Question
        exclude = ['polymorphic_ctype', 'created', 'modified', 'order']

    question_set = FilterSet
