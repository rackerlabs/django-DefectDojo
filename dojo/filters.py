__author__ = 'Jay Paz'
import collections
from datetime import timedelta, datetime

from auditlog.models import LogEntry
from django.contrib.auth.models import User
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django_filters import FilterSet, CharFilter, OrderingFilter, \
    ModelMultipleChoiceFilter, ModelChoiceFilter, MultipleChoiceFilter, \
    BooleanFilter
from django_filters.filters import ChoiceFilter, _truncate, DateTimeFilter
from pytz import timezone

from dojo.models import Dojo_User, Product_Type, Finding, Product, Test_Type, \
    Endpoint, Development_Environment, Finding_Template, Report, Note_Type
from dojo.utils import get_system_setting

local_tz = timezone(get_system_setting('time_zone'))

SEVERITY_CHOICES = (('Info', 'Info'), ('Low', 'Low'), ('Medium', 'Medium'),
                    ('High', 'High'), ('Critical', 'Critical'))
BOOLEAN_CHOICES = (('false', 'No'), ('true', 'Yes'),)

EARLIEST_FINDING = None


def now():
    return local_tz.localize(datetime.today())


def get_earliest_finding():
    global EARLIEST_FINDING
    if EARLIEST_FINDING is not None:
        return EARLIEST_FINDING

    try:
        EARLIEST_FINDING = Finding.objects.earliest('date')
    except Finding.DoesNotExist:
        EARLIEST_FINDING = None
    return EARLIEST_FINDING


class DojoFilter(FilterSet):
    def __init__(self, *args, **kwargs):
        super(DojoFilter, self).__init__(*args, **kwargs)


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


class MitigatedDateRangeFilter(ChoiceFilter):
    options = {
        '': (_('Either'), lambda qs, name: qs.all()),
        1: (_('Yes'), lambda qs, name: qs.filter(**{
            '%s__isnull' % name: False
        })),
        2: (_('No'), lambda qs, name: qs.filter(**{
            '%s__isnull' % name: True
        })),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(MitigatedDateRangeFilter, self).__init__(*args, **kwargs)

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

    def accpeted(self, qs, name):
        return qs.filter(risk_acceptance__isnull=False)

    def not_accpeted(self, qs, name):
        return qs.filter(risk_acceptance__isnull=True)

    options = {
        '': (_('Either'), any),
        1: (_('Yes'), accpeted),
        2: (_('No'), not_accpeted),
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
        if get_earliest_finding() is not None:
            start_date = local_tz.localize(datetime.combine(
                get_earliest_finding().date, datetime.min.time())
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
        if get_earliest_finding() is not None:
            start_date = local_tz.localize(datetime.combine(
                get_earliest_finding().date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](self, qs, self.field_name)


class EngagementFilter(DojoFilter):
    engagement__lead = ModelChoiceFilter(
        queryset=User.objects.filter(
            engagement__lead__isnull=False).distinct(),
        label="Lead")
    name = CharFilter(lookup_expr='icontains')
    prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by('name'),
        label="Product Type")

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

    class Meta:
        model = Product
        fields = ['name', 'prod_type']


class ProductFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains', label="Product Name")
    prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by('name'),
        label="Product Type")
    business_criticality = MultipleChoiceFilter(choices=Product.BUSINESS_CRITICALITY_CHOICES)
    platform = MultipleChoiceFilter(choices=Product.PLATFORM_CHOICES)
    lifecycle = MultipleChoiceFilter(choices=Product.LIFECYCLE_CHOICES)
    origin = MultipleChoiceFilter(choices=Product.ORIGIN_CHOICES)
    external_audience = BooleanFilter(field_name='external_audience')
    internet_accessible = BooleanFilter(field_name='internet_accessible')
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

        if self.user is not None and not self.user.is_staff:
            self.form.fields[
                'prod_type'].queryset = Product_Type.objects.filter(
                prod_type__authorized_users__in=[self.user])

    class Meta:
        model = Product
        fields = ['name', 'prod_type', 'business_criticality', 'platform', 'lifecycle', 'origin', 'external_audience',
                  'internet_accessible', ]
        exclude = ['tags']


class OpenFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains')
    duplicate = ReportBooleanFilter()
    # sourcefile = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr='icontains')
    param = CharFilter(lookup_expr='icontains')
    payload = CharFilter(lookup_expr='icontains')
    date = DateRangeFilter()
    last_reviewed = DateRangeFilter()
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(
        queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(),
        label="Product")
    if get_system_setting('enable_jira'):
        jira_issue = BooleanFilter(field_name='jira_issue',
                                   lookup_expr='isnull',
                                   exclude=True,
                                   label='JIRA issue')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('numerical_severity', 'numerical_severity'),
            ('date', 'date'),
            ('last_reviewed', 'last_reviewed'),
            ('title', 'title'),
            ('test__engagement__product__name',
             'test__engagement__product__name'),
        ),

    )

    class Meta:
        model = Finding
        exclude = ['url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template',
                   'thread_id', 'notes', 'scanner_confidence', 'mitigated',
                   'numerical_severity', 'reporter', 'last_reviewed', 'line',
                   'duplicate_finding', 'hash_code', 'images',
                   'line_number', 'reviewers', 'mitigated_by', 'sourcefile', 'jira_creation', 'jira_change', 'created']

    def __init__(self, *args, **kwargs):
        self.user = None
        self.pid = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')

        if 'pid' in kwargs:
            self.pid = kwargs.pop('pid')
        super(OpenFindingFilter, self).__init__(*args, **kwargs)

        cwe = dict()
        cwe = dict([cwe, cwe]
                   for cwe in self.queryset.values_list('cwe', flat=True).distinct()
                   if type(cwe) is int and cwe is not None and cwe > 0)
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields['cwe'].choices = list(cwe.items())
        if self.user is not None and not self.user.is_staff:
            if self.form.fields.get('test__engagement__product'):
                qs = Product.objects.filter(authorized_users__in=[self.user])
                self.form.fields['test__engagement__product'].queryset = qs
            self.form.fields['endpoints'].queryset = Endpoint.objects.filter(
                product__authorized_users__in=[self.user]).distinct()

        # Don't show the product filter on the product finding view
        if self.pid:
            del self.form.fields['test__engagement__product']


class OpenFindingSuperFilter(OpenFindingFilter):
    reporter = ModelMultipleChoiceFilter(
        queryset=Dojo_User.objects.all())
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by('name'),
        label="Product Type")


class ClosedFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains')
    sourcefile = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr='icontains')
    param = CharFilter(lookup_expr='icontains')
    payload = CharFilter(lookup_expr='icontains')
    mitigated = DateRangeFilter(label="Mitigated Date")
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(
        queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(),
        label="Product")
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(),
        label="Product Type")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('numerical_severity', 'numerical_severity'),
            ('date', 'date'),
            ('mitigated', 'mitigated'),
            ('title', 'title'),
            ('test__engagement__product__name',
             'test__engagement__product__name'),
        ),
        field_labels={
            'numerical_severity': 'Severity',
            'date': 'Date',
            'mitigated': 'Mitigated Date',
            'title': 'Finding Name',
            'test__engagement__product__name': 'Product Name',
        }

    )

    class Meta:
        model = Finding
        exclude = ['url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template',
                   'active', 'verified', 'out_of_scope', 'false_p',
                   'duplicate', 'thread_id', 'date', 'notes',
                   'numerical_severity', 'reporter', 'endpoints',
                   'last_reviewed', 'review_requested_by', 'defect_review_requested_by',
                   'last_reviewed_by', 'created', 'jira_creation', 'jira_change']

    def __init__(self, *args, **kwargs):
        super(ClosedFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict([cwe, cwe]
                   for cwe in self.queryset.values_list('cwe', flat=True).distinct()
                   if type(cwe) is int and cwe is not None and cwe > 0)
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields['cwe'].choices = list(cwe.items())


class ClosedFindingSuperFilter(ClosedFindingFilter):
    reporter = ModelMultipleChoiceFilter(
        queryset=Dojo_User.objects.all())


class AcceptedFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains')
    sourcefile = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr='icontains')
    param = CharFilter(lookup_expr='icontains')
    payload = CharFilter(lookup_expr='icontains')
    test__engagement__risk_acceptance__created = \
        DateRangeFilter(label="Acceptance Date")
    date = DateRangeFilter(label="Finding Date")
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(
        queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(),
        label="Product")
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(),
        label="Product Type")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('numerical_severity', 'numerical_severity'),
            ('date', 'date'),
            ('test__engagement__risk_acceptance__created',
             'test__engagement__risk_acceptance__created'),
            ('title', 'title'),
            ('test__engagement__product__name',
             'test__engagement__product__name'),
        ),
        field_labels={
            'numerical_severity': 'Severity',
            'date': 'Finding Date',
            'test__engagement__risk_acceptance__created': 'Acceptance Date',
            'title': 'Finding Name',
            'test__engagement__product__name': 'Product Name',
        }

    )

    class Meta:
        model = Finding
        fields = ['title', 'test__engagement__risk_acceptance__created']
        exclude = ['url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template',
                   'active', 'verified', 'out_of_scope', 'false_p',
                   'duplicate', 'thread_id', 'mitigated', 'notes',
                   'numerical_severity', 'reporter', 'endpoints',
                   'last_reviewed', 'o', 'jira_creation', 'jira_change']

    def __init__(self, *args, **kwargs):
        super(AcceptedFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict([finding.cwe, finding.cwe]
                   for finding in self.queryset.distinct()
                   if type(finding.cwe) is int and finding.cwe is not None and finding.cwe > 0 and finding.cwe not in cwe)
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields['cwe'].choices = list(cwe.items())


class AcceptedFindingSuperFilter(AcceptedFindingFilter):
    test__engagement__risk_acceptance__reporter = \
        ModelMultipleChoiceFilter(
            queryset=Dojo_User.objects.all(),
            label="Risk Acceptance Reporter")


class ProductFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains')
    sourcefile = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr='icontains')
    param = CharFilter(lookup_expr='icontains')
    payload = CharFilter(lookup_expr='icontains')
    date = DateRangeFilter()
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(
        queryset=Test_Type.objects.all())

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('numerical_severity', 'numerical_severity'),
            ('date', 'date'),
            ('test__engagement__risk_acceptance__created',
             'test__engagement__risk_acceptance__created'),
            ('title', 'title'),
            ('test__engagement__product__name',
             'test__engagement__product__name'),
        ),
        field_labels={
            'numerical_severity': 'Severity',
            'date': 'Finding Date',
            'test__engagement__risk_acceptance__created': 'Acceptance Date',
            'title': 'Finding Name',
            'test__engagement__product__name': 'Product Name',
        }

    )

    class Meta:
        model = Finding
        exclude = ['url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template',
                   'active', 'verified', 'out_of_scope', 'false_p',
                   'duplicate_finding', 'thread_id', 'mitigated', 'notes',
                   'numerical_severity', 'reporter', 'endpoints',
                   'last_reviewed', 'jira_creation', 'jira_change']

    def __init__(self, *args, **kwargs):
        super(ProductFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict([finding.cwe, finding.cwe]
                   for finding in self.queryset.distinct()
                   if type(finding.cwe) is int and finding.cwe is not None and finding.cwe > 0 and finding.cwe not in cwe)
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields['cwe'].choices = list(cwe.items())


class TemplateFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains')
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=[])
    numerical_severity = MultipleChoiceFilter(choices=[])

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

    def __init__(self, *args, **kwargs):
        super(TemplateFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict([finding.cwe, finding.cwe]
                   for finding in self.queryset.distinct()
                   if type(finding.cwe) is int and finding.cwe is not None and finding.cwe > 0 and finding.cwe not in cwe)
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields['cwe'].choices = list(cwe.items())

        self.form.fields['severity'].choices = (('Critical', 'Critical'),
                                                ('High', 'High'),
                                                ('Medium', 'Medium'),
                                                ('Low', 'Low'),
                                                ('Info', 'Info'))

        self.form.fields['numerical_severity'].choices = (('S0', 'S0'),
                                                          ('S1', 'S1'),
                                                          ('S2', 'S2'),
                                                          ('S3', 'S3'),
                                                          ('S4', 'S4'))


class FindingStatusFilter(ChoiceFilter):
    def any(self, qs, name):
        return qs.filter(verified=True,
                         false_p=False,
                         duplicate=False,
                         out_of_scope=False)

    def open(self, qs, name):
        return qs.filter(mitigated__isnull=True,
                         verified=True,
                         false_p=False,
                         duplicate=False,
                         out_of_scope=False, )

    def closed(self, qs, name):
        return qs.filter(mitigated__isnull=False,
                         verified=True,
                         false_p=False,
                         duplicate=False,
                         out_of_scope=False, )

    options = {
        '': (_('Any'), any),
        0: (_('Open'), open),
        1: (_('Closed'), closed),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(FindingStatusFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        if get_earliest_finding() is not None:
            start_date = local_tz.localize(datetime.combine(
                get_earliest_finding().date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](self, qs, self.field_name)


class MetricsFindingFilter(FilterSet):
    date = MetricsDateRangeFilter()
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by('name'),
        label="Product Type")
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    status = FindingStatusFilter(label='Status')

    def __init__(self, *args, **kwargs):
        super(MetricsFindingFilter, self).__init__(*args, **kwargs)
        self.form.fields['severity'].choices = self.queryset.order_by(
            'numerical_severity'
        ).values_list('severity', 'severity').distinct()

    class Meta:
        model = Finding
        exclude = ['url',
                   'description',
                   'mitigation',
                   'unsaved_endpoints',
                   'unsaved_request',
                   'unsaved_response',
                   'unsaved_tags',
                   'references',
                   'review_requested_by',
                   'reviewers',
                   'defect_review_requested_by',
                   'thread_id',
                   'notes',
                   'last_reviewed_by',
                   'images',
                   'endpoints',
                   'is_template',
                   'jira_creation',
                   'jira_change']


class EndpointFilter(DojoFilter):
    product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all().order_by('name'),
        label="Product")
    host = CharFilter(lookup_expr='icontains')
    path = CharFilter(lookup_expr='icontains')
    query = CharFilter(lookup_expr='icontains')
    fragment = CharFilter(lookup_expr='icontains')
    remediated = CharFilter(lookup_expr='icontains')

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
        if self.user and not self.user.is_staff:
            self.form.fields['product'].queryset = Product.objects.filter(
                authorized_users__in=[self.user]).distinct().order_by('name')

    class Meta:
        model = Endpoint
        exclude = ['remediated']


class EndpointReportFilter(DojoFilter):
    host = CharFilter(lookup_expr='icontains')
    path = CharFilter(lookup_expr='icontains')
    query = CharFilter(lookup_expr='icontains')
    fragment = CharFilter(lookup_expr='icontains')
    finding__severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    finding__mitigated = MitigatedDateRangeFilter()

    class Meta:
        model = Endpoint
        exclude = ['product']


class ReportFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains', label='Name')
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    active = ReportBooleanFilter()
    mitigated = MitigatedDateRangeFilter()
    verified = ReportBooleanFilter()
    false_p = ReportBooleanFilter(label="False Positive")
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted")
    duplicate = ReportBooleanFilter()
    out_of_scope = ReportBooleanFilter()

    class Meta:
        model = Finding
        exclude = ['date', 'cwe', 'url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template',
                   'thread_id', 'notes', 'endpoints',
                   'numerical_severity', 'reporter', 'last_reviewed', 'images', 'jira_creation', 'jira_change']


class ReportAuthedFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr='icontains', label='Name')
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product")
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(),
        label="Product Type")
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    active = ReportBooleanFilter()
    mitigated = MitigatedDateRangeFilter()
    verified = ReportBooleanFilter()
    false_p = ReportBooleanFilter(label="False Positive")
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted")
    duplicate = ReportBooleanFilter()
    out_of_scope = ReportBooleanFilter()

    def __init__(self, *args, **kwargs):
        self.user = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')
        super(ReportAuthedFindingFilter, self).__init__(*args, **kwargs)
        if not self.user.is_staff:
            self.form.fields[
                'test__engagement__product'].queryset = Product.objects.filter(
                authorized_users__in=[self.user])

    @property
    def qs(self):
        parent = super(ReportAuthedFindingFilter, self).qs
        if self.user.is_staff:
            return parent
        else:
            return parent.filter(
                test__engagement__product__authorized_users__in=[self.user])

    class Meta:
        model = Finding
        exclude = ['date', 'cwe', 'url', 'description', 'mitigation', 'impact',
                   'endpoint', 'references', 'test', 'is_template',
                   'thread_id', 'notes', 'endpoints',
                   'numerical_severity', 'reporter', 'last_reviewed', 'jira_creation', 'jira_change']


class UserFilter(DojoFilter):
    first_name = CharFilter(lookup_expr='icontains')
    last_name = CharFilter(lookup_expr='icontains')
    username = CharFilter(lookup_expr='icontains')

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


class ReportFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')
    type = MultipleChoiceFilter(choices=[])
    format = MultipleChoiceFilter(choices=[])
    requester = ModelMultipleChoiceFilter(queryset=Dojo_User.objects.all())
    datetime = DateTimeFilter()
    status = MultipleChoiceFilter(choices=[])

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('datetime', 'datetime'),
            ('name', 'name'),
            ('type', 'type'),
            ('format', 'format'),
            ('requester', 'requester'),
        ),
        field_labels={
            'datetime': 'Date',
        }

    )

    class Meta:
        model = Report
        exclude = ['task_id', 'file']

    def __init__(self, *args, **kwargs):
        super(ReportFilter, self).__init__(*args, **kwargs)
        type = dict()
        type = dict(
            [report.type, report.type] for report in self.queryset.distinct()
            if report.type is not None)
        type = collections.OrderedDict(sorted(type.items()))
        self.form.fields['type'].choices = list(type.items())

        status = dict()
        status = dict(
            [report.status, report.status] for report in
            self.queryset.distinct() if report.status is not None)
        status = collections.OrderedDict(sorted(status.items()))
        self.form.fields['status'].choices = list(status.items())


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
        exclude = []
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


class CommonNoteFilter(DojoFilter):
    name = CharFilter(lookup_expr='icontains')

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('scanner', 'scanner'),
            ('title', 'title'),
            ('cwe', 'cwe'),
            ('product', 'product'),
            ('notes', 'notes'),
        ),
    )

    class Meta:
        model = Note_Type
        exclude = []
        include = ('name', 'is_single', 'description')
