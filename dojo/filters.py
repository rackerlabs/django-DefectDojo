__author__ = "Jay Paz"
import collections
import logging
from datetime import timedelta, datetime
from django.apps import apps
from auditlog.models import LogEntry
from django.contrib.auth.models import User
import six
from django.utils.translation import ugettext_lazy as _
from django_filters import (
    FilterSet,
    CharFilter,
    OrderingFilter,
    ModelMultipleChoiceFilter,
    ModelChoiceFilter,
    MultipleChoiceFilter,
    BooleanFilter,
    NumberFilter,
    DateFilter,
)
from django_filters import rest_framework as filters
from django_filters.filters import ChoiceFilter, _truncate, DateTimeFilter
import pytz
from django.db.models import Q
from dojo.models import (
    Dojo_User,
    Product_Type,
    Finding,
    Product,
    Test_Type,
    Endpoint,
    Development_Environment,
    Finding_Template,
    Report,
    Note_Type,
    Engagement_Survey,
    Question,
    TextQuestion,
    ChoiceQuestion,
    Endpoint_Status,
    Engagement,
    ENGAGEMENT_STATUS_CHOICES,
    Test,
    App_Analysis,
)
from dojo.utils import get_system_setting
from django.contrib.contenttypes.models import ContentType
import tagulous

# from tagulous.forms import TagWidget
# import tagulous
from crum import get_current_user

logger = logging.getLogger(__name__)

local_tz = pytz.timezone(get_system_setting("time_zone"))

SEVERITY_CHOICES = (
    ("Info", "Info"),
    ("Low", "Low"),
    ("Medium", "Medium"),
    ("High", "High"),
    ("Critical", "Critical"),
)
BOOLEAN_CHOICES = (
    ("false", "No"),
    ("true", "Yes"),
)
EARLIEST_FINDING = None


def custom_filter(queryset, name, value):
    values = value.split(",")
    filter = "%s__in" % (name)
    return queryset.filter(Q(**{filter: values}))


def now():
    return local_tz.localize(datetime.today())


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class CharFieldInFilter(filters.BaseInFilter, filters.CharFilter):
    def __init__(self, *args, **kwargs):
        super(CharFilter, self).__init__(*args, **kwargs)


def get_earliest_finding(queryset=None):
    if queryset is None:  # don't to 'if not queryset' which will trigger the query
        queryset = Finding.objects.all()

    try:
        EARLIEST_FINDING = queryset.earliest("date")
    except Finding.DoesNotExist:
        EARLIEST_FINDING = None
    return EARLIEST_FINDING


class DojoFilter(FilterSet):
    def __init__(self, *args, **kwargs):
        super(DojoFilter, self).__init__(*args, **kwargs)

        # for now we have only fields called "tags"
        for field in [
            "tags",
            "test__tags",
            "test__engagement__tags",
            "test__engagement__product__tags",
        ]:
            if field in self.form.fields:
                tags_filter = self.filters["tags"]
                model = tags_filter.model

                self.form.fields[field] = model._meta.get_field("tags").formfield()
                self.form.fields[field].widget.tag_options = self.form.fields[
                    field
                ].widget.tag_options + tagulous.models.options.TagOptions(
                    autocomplete_settings={"width": "200px"}
                )
                tagged_model = get_tags_model_from_field_name(field)
                if tagged_model:  # only if not the normal tags field
                    self.form.fields[field].label = get_tags_label_from_model(
                        tagged_model
                    )
                    self.form.fields[
                        field
                    ].autocomplete_tags = tagged_model.tags.tag_model.objects.all().order_by(
                        "name"
                    )


def get_tags_model_from_field_name(field):
    try:
        parts = field.split("__")
        model_name = parts[-2]
        return apps.get_model("dojo.%s" % model_name, require_ready=True)
    except Exception as e:
        return None


def get_tags_label_from_model(model):
    if model:
        return "Tags (%s)" % model.__name__.title()
    else:
        return "Tags (Unknown)"


class DateRangeFilter(ChoiceFilter):
    options = {
        "": (_("Any date"), lambda qs, name: qs.all()),
        1: (
            _("Today"),
            lambda qs, name: qs.filter(
                **{
                    "%s__year" % name: now().year,
                    "%s__month" % name: now().month,
                    "%s__day" % name: now().day,
                }
            ),
        ),
        2: (
            _("Past 7 days"),
            lambda qs, name: qs.filter(
                **{
                    "%s__gte" % name: _truncate(now() - timedelta(days=7)),
                    "%s__lt" % name: _truncate(now() + timedelta(days=1)),
                }
            ),
        ),
        3: (
            _("Past 30 days"),
            lambda qs, name: qs.filter(
                **{
                    "%s__gte" % name: _truncate(now() - timedelta(days=30)),
                    "%s__lt" % name: _truncate(now() + timedelta(days=1)),
                }
            ),
        ),
        4: (
            _("Past 90 days"),
            lambda qs, name: qs.filter(
                **{
                    "%s__gte" % name: _truncate(now() - timedelta(days=90)),
                    "%s__lt" % name: _truncate(now() + timedelta(days=1)),
                }
            ),
        ),
        5: (
            _("Current month"),
            lambda qs, name: qs.filter(
                **{"%s__year" % name: now().year, "%s__month" % name: now().month}
            ),
        ),
        6: (
            _("Current year"),
            lambda qs, name: qs.filter(
                **{
                    "%s__year" % name: now().year,
                }
            ),
        ),
        7: (
            _("Past year"),
            lambda qs, name: qs.filter(
                **{
                    "%s__gte" % name: _truncate(now() - timedelta(days=365)),
                    "%s__lt" % name: _truncate(now() + timedelta(days=1)),
                }
            ),
        ),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(DateRangeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
        return self.options[value][1](qs, self.field_name)


class MitigatedDateRangeFilter(ChoiceFilter):
    options = {
        "": (_("Either"), lambda qs, name: qs.all()),
        1: (_("Yes"), lambda qs, name: qs.filter(**{"%s__isnull" % name: False})),
        2: (_("No"), lambda qs, name: qs.filter(**{"%s__isnull" % name: True})),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(MitigatedDateRangeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
        return self.options[value][1](qs, self.field_name)


class ReportBooleanFilter(ChoiceFilter):
    options = {
        "": (_("Either"), lambda qs, name: qs.all()),
        1: (_("Yes"), lambda qs, name: qs.filter(**{"%s" % name: True})),
        2: (_("No"), lambda qs, name: qs.filter(**{"%s" % name: False})),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(ReportBooleanFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
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
        "": (_("Either"), any),
        1: (_("Yes"), accepted),
        2: (_("No"), not_accepted),
        3: (_("Was"), was_accepted),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(ReportRiskAcceptanceFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
        return self.options[value][1](self, qs, self.field_name)


class MetricsDateRangeFilter(ChoiceFilter):
    def any(self, qs, name):
        earliest_finding = get_earliest_finding(qs)
        if earliest_finding is not None:
            start_date = local_tz.localize(
                datetime.combine(earliest_finding.date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
            return qs.all()

    def current_month(self, qs, name):
        self.start_date = local_tz.localize(
            datetime(now().year, now().month, 1, 0, 0, 0)
        )
        self.end_date = now()
        return qs.filter(
            **{
                "%s__year" % name: self.start_date.year,
                "%s__month" % name: self.start_date.month,
            }
        )

    def current_year(self, qs, name):
        self.start_date = local_tz.localize(datetime(now().year, 1, 1, 0, 0, 0))
        self.end_date = now()
        return qs.filter(
            **{
                "%s__year" % name: now().year,
            }
        )

    def past_x_days(self, qs, name, days):
        self.start_date = _truncate(now() - timedelta(days=days))
        self.end_date = _truncate(now() + timedelta(days=1))
        return qs.filter(
            **{
                "%s__gte" % name: self.start_date,
                "%s__lt" % name: self.end_date,
            }
        )

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
        "": (_("Past 30 days"), past_thirty_days),
        1: (_("Past 7 days"), past_seven_days),
        2: (_("Past 90 days"), past_ninety_days),
        3: (_("Current month"), current_month),
        4: (_("Current year"), current_year),
        5: (_("Past 6 Months"), past_six_months),
        6: (_("Past year"), past_year),
        7: (_("Any date"), any),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(MetricsDateRangeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        if value == 8:
            return qs
        earliest_finding = get_earliest_finding(qs)
        if earliest_finding is not None:
            start_date = local_tz.localize(
                datetime.combine(earliest_finding.date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
        return self.options[value][1](self, qs, self.field_name)


class ProductComponentFilter(DojoFilter):
    component_name = CharFilter(lookup_expr="icontains", label="Module Name")
    component_version = CharFilter(lookup_expr="icontains", label="Module Version")

    o = OrderingFilter(
        fields=(
            ("component_name", "component_name"),
            ("component_version", "component_version"),
            ("active", "active"),
            ("duplicate", "duplicate"),
            ("total", "total"),
        ),
        field_labels={
            "component_name": "Component Name",
            "component_version": "Component Version",
            "active": "Active",
            "duplicate": "Duplicate",
            "total": "Total",
        },
    )


class ComponentFilter(ProductComponentFilter):
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by("name"), label="Product Type"
    )
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product"
    )


class EngagementFilter(DojoFilter):
    engagement__lead = ModelChoiceFilter(
        queryset=User.objects.filter(engagement__lead__isnull=False).distinct(),
        label="Lead",
    )
    engagement__version = CharFilter(
        field_name="engagement__version",
        lookup_expr="icontains",
        label="Engagement version",
    )
    engagement__test__version = CharFilter(
        field_name="engagement__test__version",
        lookup_expr="icontains",
        label="Test version",
    )

    name = CharFilter(lookup_expr="icontains")
    prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by("name"), label="Product Type"
    )
    engagement__status = MultipleChoiceFilter(
        choices=ENGAGEMENT_STATUS_CHOICES, label="Status"
    )

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("name", "name"),
            ("prod_type__name", "prod_type__name"),
        ),
        field_labels={
            "name": "Product Name",
            "prod_type__name": "Product Type",
        },
    )

    class Meta:
        model = Product
        fields = ["name", "prod_type"]


class ApiEngagementFilter(DojoFilter):
    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    class Meta:
        model = Engagement
        fields = [
            "id",
            "active",
            "eng_type",
            "target_start",
            "target_end",
            "requester",
            "report_type",
            "updated",
            "threat_model",
            "api_test",
            "pen_test",
            "status",
            "product",
            "name",
            "version",
            "tags",
        ]


class ProductFilter(DojoFilter):
    name = CharFilter(lookup_expr="icontains", label="Product Name")
    prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by("name"), label="Product Type"
    )
    business_criticality = MultipleChoiceFilter(
        choices=Product.BUSINESS_CRITICALITY_CHOICES
    )
    platform = MultipleChoiceFilter(choices=Product.PLATFORM_CHOICES)
    lifecycle = MultipleChoiceFilter(choices=Product.LIFECYCLE_CHOICES)
    origin = MultipleChoiceFilter(choices=Product.ORIGIN_CHOICES)
    external_audience = BooleanFilter(field_name="external_audience")
    internet_accessible = BooleanFilter(field_name="internet_accessible")

    # not specifying anything for tags will render a multiselect input functioning as OR

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
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

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag contains"
    )

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

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("name", "name"),
            ("prod_type__name", "prod_type__name"),
            ("business_criticality", "business_criticality"),
            ("platform", "platform"),
            ("lifecycle", "lifecycle"),
            ("origin", "origin"),
            ("external_audience", "external_audience"),
            ("internet_accessible", "internet_accessible"),
        ),
        field_labels={
            "name": "Product Name",
            "prod_type__name": "Product Type",
            "business_criticality": "Business Criticality",
            "platform": "Platform ",
            "lifecycle": "Lifecycle ",
            "origin": "Origin ",
            "external_audience": "External Audience ",
            "internet_accessible": "Internet Accessible ",
        },
    )

    # tags = CharFilter(lookup_expr='icontains', label="Tags")

    def __init__(self, *args, **kwargs):
        self.user = None
        if "user" in kwargs:
            self.user = kwargs.pop("user")

        super(ProductFilter, self).__init__(*args, **kwargs)

        if self.user is not None and not self.user.is_staff:
            self.form.fields["prod_type"].queryset = Product_Type.objects.filter(
                authorized_users__in=[self.user]
            )

    class Meta:
        model = Product
        fields = [
            "name",
            "prod_type",
            "business_criticality",
            "platform",
            "lifecycle",
            "origin",
            "external_audience",
            "internet_accessible",
            "tags",
        ]


class ApiProductFilter(DojoFilter):
    # BooleanFilter
    duplicate = BooleanFilter(field_name="duplicate")
    external_audience = BooleanFilter(field_name="external_audience")
    internet_accessible = BooleanFilter(field_name="internet_accessible")
    # CharFilter
    name = CharFilter(lookup_expr="icontains")
    description = CharFilter(lookup_expr="icontains")
    business_criticality = CharFilter(
        method=custom_filter, field_name="business_criticality"
    )
    platform = CharFilter(method=custom_filter, field_name="platform")
    lifecycle = CharFilter(method=custom_filter, field_name="lifecycle")
    origin = CharFilter(method=custom_filter, field_name="origin")
    # NumberInFilter
    id = NumberInFilter(field_name="id", lookup_expr="in")
    product_manager = NumberInFilter(field_name="product_manager", lookup_expr="in")
    technical_contact = NumberInFilter(field_name="technical_contact", lookup_expr="in")
    team_manager = NumberInFilter(field_name="team_manager", lookup_expr="in")
    prod_type = NumberInFilter(field_name="prod_type", lookup_expr="in")
    tid = NumberInFilter(field_name="tid", lookup_expr="in")
    authorized_users = NumberInFilter(field_name="authorized_users", lookup_expr="in")
    prod_numeric_grade = NumberInFilter(
        field_name="prod_numeric_grade", lookup_expr="in"
    )
    user_records = NumberInFilter(field_name="user_records", lookup_expr="in")
    regulations = NumberInFilter(field_name="regulations", lookup_expr="in")
    active_finding_count = NumberInFilter(
        field_name="active_finding_count", lookup_expr="in"
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    # DateRangeFilter
    created = DateRangeFilter()
    updated = DateRangeFilter()
    # NumberFilter
    revenue = NumberFilter()

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("id", "id"),
            ("tid", "tid"),
            ("name", "name"),
            ("created", "created"),
            ("prod_numeric_grade", "prod_numeric_grade"),
            ("business_criticality", "business_criticality"),
            ("platform", "platform"),
            ("lifecycle", "lifecycle"),
            ("origin", "origin"),
            ("revenue", "revenue"),
            ("external_audience", "external_audience"),
            ("internet_accessible", "internet_accessible"),
            ("product_manager", "product_manager"),
            ("product_manager__first_name", "product_manager__first_name"),
            ("product_manager__last_name", "product_manager__last_name"),
            ("technical_contact", "technical_contact"),
            ("technical_contact__first_name", "technical_contact__first_name"),
            ("technical_contact__last_name", "technical_contact__last_name"),
            ("team_manager", "team_manager"),
            ("team_manager__first_name", "team_manager__first_name"),
            ("team_manager__last_name", "team_manager__last_name"),
            ("prod_type", "prod_type"),
            ("prod_type__name", "prod_type__name"),
            ("updated", "updated"),
            ("user_records", "user_records"),
        )
    )


class ApiFindingFilter(DojoFilter):
    # BooleanFilter
    active = BooleanFilter(field_name="active")
    duplicate = BooleanFilter(field_name="duplicate")
    dynamic_finding = BooleanFilter(field_name="dynamic_finding")
    false_p = BooleanFilter(field_name="false_p")
    is_Mitigated = BooleanFilter(field_name="is_Mitigated")
    out_of_scope = BooleanFilter(field_name="out_of_scope")
    static_finding = BooleanFilter(field_name="static_finding")
    under_defect_review = BooleanFilter(field_name="under_defect_review")
    under_review = BooleanFilter(field_name="under_review")
    verified = BooleanFilter(field_name="verified")
    # CharFilter
    component_version = CharFilter(lookup_expr="icontains")
    component_name = CharFilter(lookup_expr="icontains")
    cve = CharFilter(method=custom_filter, field_name="cve")
    description = CharFilter(lookup_expr="icontains")
    file_path = CharFilter(lookup_expr="icontains")
    hash_code = CharFilter(lookup_expr="icontains")
    impact = CharFilter(lookup_expr="icontains")
    mitigation = CharFilter(lookup_expr="icontains")
    numerical_severity = CharFilter(
        method=custom_filter, field_name="numerical_severity"
    )
    param = CharFilter(lookup_expr="icontains")
    payload = CharFilter(lookup_expr="icontains")
    references = CharFilter(lookup_expr="icontains")
    severity = CharFilter(method=custom_filter, field_name="severity")
    severity_justification = CharFilter(lookup_expr="icontains")
    step_to_reproduce = CharFilter(lookup_expr="icontains")
    sourcefile = CharFilter(lookup_expr="icontains")
    sourcefilepath = CharFilter(lookup_expr="icontains")
    unique_id_from_tool = CharFilter(lookup_expr="icontains")
    title = CharFilter(lookup_expr="icontains")
    # DateRangeFilter
    created = DateRangeFilter()
    date = DateRangeFilter()
    jira_creation = DateRangeFilter(field_name="jira_issue__jira_creation")
    jira_change = DateRangeFilter(field_name="jira_issue__jira_change")
    last_reviewed = DateRangeFilter()
    mitigated = DateRangeFilter()
    # NumberInFilter
    cwe = NumberInFilter(field_name="cwe", lookup_expr="in")
    defect_review_requested_by = NumberInFilter(
        field_name="defect_review_requested_by", lookup_expr="in"
    )
    endpoints = NumberInFilter(field_name="endpoints", lookup_expr="in")
    found_by = NumberInFilter(field_name="found_by", lookup_expr="in")
    id = NumberInFilter(field_name="id", lookup_expr="in")
    last_reviewed_by = NumberInFilter(field_name="last_reviewed_by", lookup_expr="in")
    mitigated_by = NumberInFilter(field_name="mitigated_by", lookup_expr="in")
    nb_occurences = NumberInFilter(field_name="nb_occurences", lookup_expr="in")
    reporter = NumberInFilter(field_name="reporter", lookup_expr="in")
    scanner_confidence = NumberInFilter(
        field_name="scanner_confidence", lookup_expr="in"
    )
    review_requested_by = NumberInFilter(
        field_name="review_requested_by", lookup_expr="in"
    )
    reviewers = NumberInFilter(field_name="reviewers", lookup_expr="in")
    sast_source_line = NumberInFilter(field_name="sast_source_line", lookup_expr="in")
    sonarqube_issue = NumberInFilter(field_name="sonarqube_issue", lookup_expr="in")
    test__test_type = NumberInFilter(field_name="test__test_type", lookup_expr="in")
    test__engagement = NumberInFilter(field_name="test__engagement", lookup_expr="in")
    test__engagement__product = NumberInFilter(
        field_name="test__engagement__product", lookup_expr="in"
    )
    # ReportRiskAcceptanceFilter
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter()

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("active", "active"),
            ("component_name", "component_name"),
            ("component_version", "component_version"),
            ("created", "created"),
            ("cve", "cve"),
            ("cwe", "cwe"),
            ("date", "date"),
            ("duplicate", "duplicate"),
            ("dynamic_finding", "dynamic_finding"),
            ("false_p", "false_p"),
            ("found_by", "found_by"),
            ("id", "id"),
            ("is_Mitigated", "is_Mitigated"),
            ("numerical_severity", "numerical_severity"),
            ("out_of_scope", "out_of_scope"),
            ("severity", "severity"),
            ("reviewers", "reviewers"),
            ("static_finding", "static_finding"),
            ("test__engagement__product__name", "test__engagement__product__name"),
            ("title", "title"),
            ("under_defect_review", "under_defect_review"),
            ("under_review", "under_review"),
            ("verified", "verified"),
        ),
    )

    class Meta:
        model = Finding
        exclude = [
            "url",
            "is_template",
            "thread_id",
            "notes",
            "images",
            "files",
            "sourcefile",
            "line",
            "endpoint_status",
            "tags_from_django_tagging",
        ]


class OpenFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains")
    duplicate = ReportBooleanFilter()
    # sourcefile = CharFilter(lookup_expr='icontains')
    sourcefilepath = CharFilter(lookup_expr="icontains")
    param = CharFilter(lookup_expr="icontains")
    payload = CharFilter(lookup_expr="icontains")
    date = DateRangeFilter()
    last_reviewed = DateRangeFilter()
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product"
    )
    test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.all(), label="Engagement"
    )
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted"
    )

    has_jira_issue = BooleanFilter(
        field_name="jira_issue", lookup_expr="isnull", exclude=True, label="has JIRA"
    )

    has_component = BooleanFilter(
        field_name="component_name",
        lookup_expr="isnull",
        exclude=True,
        label="has Component",
    )

    jira_issue__jira_key = CharFilter(
        field_name="jira_issue__jira_key", lookup_expr="icontains", label="JIRA issue"
    )

    has_notes = BooleanFilter(
        field_name="notes", lookup_expr="isnull", exclude=True, label="has notes"
    )

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("numerical_severity", "numerical_severity"),
            ("date", "date"),
            ("last_reviewed", "last_reviewed"),
            ("title", "title"),
            ("test__engagement__product__name", "test__engagement__product__name"),
        ),
    )

    class Meta:
        model = Finding
        exclude = [
            "url",
            "description",
            "mitigation",
            "impact",
            "endpoint",
            "references",
            "test",
            "is_template",
            "thread_id",
            "notes",
            "scanner_confidence",
            "mitigated",
            "numerical_severity",
            "reporter",
            "last_reviewed",
            "line",
            "duplicate_finding",
            "hash_code",
            "images",
            "endpoint_status",
            "line_number",
            "reviewers",
            "mitigated_by",
            "sourcefile",
            "created",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
            "tags",
            "files",
        ]

    def __init__(self, *args, **kwargs):
        self.user = None
        self.pid = None
        if "user" in kwargs:
            self.user = kwargs.pop("user")

        if "pid" in kwargs:
            self.pid = kwargs.pop("pid")
        super(OpenFindingFilter, self).__init__(*args, **kwargs)

        if not get_system_setting("enable_jira"):
            self.form.fields.pop("jira_issue__jira_key")
            self.form.fields.pop("has_jira_issue")

        cwe = dict()
        cwe = dict(
            [cwe, cwe]
            for cwe in self.queryset.order_by().values_list("cwe", flat=True).distinct()
            if type(cwe) is int and cwe is not None and cwe > 0
        )
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields["cwe"].choices = list(cwe.items())
        if self.user is not None and not self.user.is_staff:
            if self.form.fields.get("test__engagement__product"):
                qs = Product.objects.filter(authorized_users__in=[self.user])
                self.form.fields["test__engagement__product"].queryset = qs
            self.form.fields["endpoints"].queryset = Endpoint.objects.filter(
                product__authorized_users__in=[self.user]
            ).distinct()

        # Don't show the product filter on the product finding view
        if self.pid:
            del self.form.fields["test__engagement__product"]
            self.form.fields["test__engagement"].queryset = Engagement.objects.filter(
                product_id=self.pid
            ).all()


class OpenFindingSuperFilter(OpenFindingFilter):
    reporter = ModelMultipleChoiceFilter(queryset=Dojo_User.objects.all())
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by("name"), label="Product Type"
    )


class ClosedFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains")
    sourcefile = CharFilter(lookup_expr="icontains")
    sourcefilepath = CharFilter(lookup_expr="icontains")
    param = CharFilter(lookup_expr="icontains")
    payload = CharFilter(lookup_expr="icontains")
    mitigated = DateRangeFilter(label="Mitigated Date")
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product"
    )
    test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.all(), label="Engagement"
    )
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(), label="Product Type"
    )
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted"
    )

    has_jira_issue = BooleanFilter(
        field_name="jira_issue", lookup_expr="isnull", exclude=True, label="has JIRA"
    )

    jira_issue__jira_key = CharFilter(
        field_name="jira_issue__jira_key", lookup_expr="icontains", label="JIRA issue"
    )

    has_notes = BooleanFilter(
        field_name="notes", lookup_expr="isnull", exclude=True, label="has notes"
    )

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("numerical_severity", "numerical_severity"),
            ("date", "date"),
            ("mitigated", "mitigated"),
            ("title", "title"),
            ("test__engagement__product__name", "test__engagement__product__name"),
        ),
        field_labels={
            "numerical_severity": "Severity",
            "date": "Date",
            "mitigated": "Mitigated Date",
            "title": "Finding Name",
            "test__engagement__product__name": "Product Name",
        },
    )

    class Meta:
        model = Finding
        exclude = [
            "url",
            "description",
            "mitigation",
            "impact",
            "endpoint",
            "references",
            "test",
            "is_template",
            "active",
            "verified",
            "out_of_scope",
            "false_p",
            "duplicate",
            "duplicate_finding",
            "thread_id",
            "date",
            "notes",
            "numerical_severity",
            "reporter",
            "endpoints",
            "endpoint_status",
            "last_reviewed",
            "review_requested_by",
            "defect_review_requested_by",
            "last_reviewed_by",
            "created",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
            "files",
        ]

    def __init__(self, *args, **kwargs):
        self.pid = None
        if "pid" in kwargs:
            self.pid = kwargs.pop("pid")
        super(ClosedFindingFilter, self).__init__(*args, **kwargs)

        if not get_system_setting("enable_jira"):
            self.form.fields.pop("jira_issue__jira_key")
            self.form.fields.pop("has_jira_issue")

        cwe = dict()
        cwe = dict(
            [cwe, cwe]
            for cwe in self.queryset.values_list("cwe", flat=True).distinct()
            if type(cwe) is int and cwe is not None and cwe > 0
        )
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields["cwe"].choices = list(cwe.items())

        if self.pid:
            self.form.fields["test__engagement"].queryset = Engagement.objects.filter(
                product_id=self.pid
            ).all()


class ClosedFindingSuperFilter(ClosedFindingFilter):
    reporter = ModelMultipleChoiceFilter(queryset=Dojo_User.objects.all())


class AcceptedFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains")
    sourcefile = CharFilter(lookup_expr="icontains")
    sourcefilepath = CharFilter(lookup_expr="icontains")
    param = CharFilter(lookup_expr="icontains")
    payload = CharFilter(lookup_expr="icontains")
    test__engagement__risk_acceptance__created = DateRangeFilter(
        label="Acceptance Date"
    )
    date = DateRangeFilter(label="Finding Date")
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product"
    )
    test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.all(), label="Engagement"
    )
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(), label="Product Type"
    )

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("numerical_severity", "numerical_severity"),
            ("date", "date"),
            (
                "test__engagement__risk_acceptance__created",
                "test__engagement__risk_acceptance__created",
            ),
            ("title", "title"),
            ("test__engagement__product__name", "test__engagement__product__name"),
        ),
        field_labels={
            "numerical_severity": "Severity",
            "date": "Finding Date",
            "test__engagement__risk_acceptance__created": "Acceptance Date",
            "title": "Finding Name",
            "test__engagement__product__name": "Product Name",
        },
    )

    class Meta:
        model = Finding
        fields = ["title", "test__engagement__risk_acceptance__created"]
        exclude = [
            "url",
            "description",
            "mitigation",
            "impact",
            "endpoint",
            "references",
            "test",
            "is_template",
            "active",
            "verified",
            "out_of_scope",
            "false_p",
            "duplicate",
            "duplicate_finding",
            "thread_id",
            "mitigated",
            "notes",
            "numerical_severity",
            "reporter",
            "endpoints",
            "endpoint_status",
            "last_reviewed",
            "o",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
            "files",
        ]

    def __init__(self, *args, **kwargs):
        self.pid = None
        if "pid" in kwargs:
            self.pid = kwargs.pop("pid")
        super(AcceptedFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict(
            [finding.cwe, finding.cwe]
            for finding in self.queryset.distinct()
            if type(finding.cwe) is int
            and finding.cwe is not None
            and finding.cwe > 0
            and finding.cwe not in cwe
        )
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields["cwe"].choices = list(cwe.items())

        if self.pid:
            self.form.fields["test__engagement"].queryset = Engagement.objects.filter(
                product_id=self.pid
            ).all()


class AcceptedFindingSuperFilter(AcceptedFindingFilter):
    test__engagement__risk_acceptance__reporter = ModelMultipleChoiceFilter(
        queryset=Dojo_User.objects.all(), label="Risk Acceptance Reporter"
    )


class ProductFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains")
    sourcefile = CharFilter(lookup_expr="icontains")
    sourcefilepath = CharFilter(lookup_expr="icontains")
    param = CharFilter(lookup_expr="icontains")
    payload = CharFilter(lookup_expr="icontains")
    date = DateRangeFilter()
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    test__test_type = ModelMultipleChoiceFilter(queryset=Test_Type.objects.all())
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted"
    )

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("numerical_severity", "numerical_severity"),
            ("date", "date"),
            (
                "test__engagement__risk_acceptance__created",
                "test__engagement__risk_acceptance__created",
            ),
            ("title", "title"),
            ("test__engagement__product__name", "test__engagement__product__name"),
        ),
        field_labels={
            "numerical_severity": "Severity",
            "date": "Finding Date",
            "test__engagement__risk_acceptance__created": "Acceptance Date",
            "title": "Finding Name",
            "test__engagement__product__name": "Product Name",
        },
    )

    class Meta:
        model = Finding
        exclude = [
            "url",
            "description",
            "mitigation",
            "impact",
            "endpoint",
            "references",
            "test",
            "is_template",
            "active",
            "verified",
            "out_of_scope",
            "false_p",
            "duplicate_finding",
            "thread_id",
            "mitigated",
            "notes",
            "numerical_severity",
            "reporter",
            "endpoints",
            "endpoint_status",
            "last_reviewed",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
            "files",
        ]

    def __init__(self, *args, **kwargs):
        super(ProductFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict(
            [finding.cwe, finding.cwe]
            for finding in self.queryset.distinct()
            if type(finding.cwe) is int
            and finding.cwe is not None
            and finding.cwe > 0
            and finding.cwe not in cwe
        )
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields["cwe"].choices = list(cwe.items())


class SimilarFindingFilter(DojoFilter):
    cve = CharFilter(lookup_expr="icontains")
    cwe = NumberFilter()
    title = CharFilter(lookup_expr="icontains")
    duplicate = ReportBooleanFilter()
    # sourcefile = CharFilter(lookup_expr='icontains')
    file_path = CharFilter(lookup_expr="icontains")
    mitigated = DateRangeFilter(label="Mitigated Date")
    date = DateRangeFilter()
    component_name = CharFilter(lookup_expr="icontains")
    component_version = CharFilter(lookup_expr="icontains")

    test__test_type = ModelMultipleChoiceFilter(queryset=Test_Type.objects.all())
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product"
    )
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(), label="Product Type"
    )

    has_jira_issue = BooleanFilter(
        field_name="jira_issue", lookup_expr="isnull", exclude=True, label="has JIRA"
    )

    jira_issue__jira_key = CharFilter(
        field_name="jira_issue__jira_key", lookup_expr="icontains", label="JIRA issue"
    )

    has_notes = BooleanFilter(
        field_name="notes", lookup_expr="isnull", exclude=True, label="has notes"
    )

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("numerical_severity", "numerical_severity"),
            ("date", "date"),
            ("title", "title"),
            ("test__engagement__product__name", "test__engagement__product__name"),
        ),
    )

    class Meta:
        model = Finding
        fields = ["cwe", "hash_code", "unique_id_from_tool", "line", "id", "tags"]

    def __init__(self, data=None, *args, **kwargs):
        self.user = None
        if "user" in kwargs:
            self.user = kwargs.pop("user")

        self.finding = None
        if "finding" in kwargs:
            self.finding = kwargs.pop("finding")

        # if filterset is bound, use initial values as defaults
        if not data:
            # get a mutable copy of the QueryDict
            data = data.copy()

            data["cve"] = self.finding.cve
            data["cwe"] = self.finding.cwe
            data["file_path"] = self.finding.file_path
            data["line"] = self.finding.line
            data["unique_id_from_tool"] = self.finding.unique_id_from_tool
            data["test__test_type"] = self.finding.test.test_type
            data["test__engagement__product"] = self.finding.test.engagement.product
            data[
                "test__engagement__product__prod_type"
            ] = self.finding.test.engagement.product.prod_type

        super().__init__(data, *args, **kwargs)

        if get_system_setting("enable_jira"):
            self.form.fields.pop("jira_issue__jira_key")
            self.form.fields.pop("has_jira_issue")

        if self.user is not None and not self.user.is_staff:
            if self.form.fields.get("test__engagement__product"):
                qs = Product.objects.filter(authorized_users__in=[self.user])
                self.form.fields["test__engagement__product"].queryset = qs
            if self.form.fields.get("test__engagement__product__prod_type"):
                qs = Product_Type.objects.filter(authorized_users__in=[self.user])
                self.form.fields["test__engagement__product__prod_type"].queryset = qs

    def filter_queryset(self, *args, **kwargs):
        queryset = super().filter_queryset(*args, **kwargs)
        if not self.user.is_staff:
            queryset = queryset.filter(
                Q(test__engagement__product__authorized_users__in=[self.user])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        self.user
                    ]
                )
            )
        queryset = queryset.exclude(pk=self.finding.pk)
        return queryset


class TemplateFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains")
    cwe = MultipleChoiceFilter(choices=[])
    severity = MultipleChoiceFilter(choices=[])
    numerical_severity = MultipleChoiceFilter(choices=[])

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding_Template.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("cwe", "cwe"),
            ("title", "title"),
            ("numerical_severity", "numerical_severity"),
        ),
        field_labels={
            "numerical_severity": "Severity",
        },
    )

    class Meta:
        model = Finding_Template
        exclude = [
            "description",
            "mitigation",
            "impact",
            "references",
            "numerical_severity",
            "tags_from_django_tagging",
        ]

    def __init__(self, *args, **kwargs):
        super(TemplateFindingFilter, self).__init__(*args, **kwargs)
        cwe = dict()
        cwe = dict(
            [finding.cwe, finding.cwe]
            for finding in self.queryset.distinct()
            if type(finding.cwe) is int
            and finding.cwe is not None
            and finding.cwe > 0
            and finding.cwe not in cwe
        )
        cwe = collections.OrderedDict(sorted(cwe.items()))
        self.form.fields["cwe"].choices = list(cwe.items())

        self.form.fields["severity"].choices = (
            ("Critical", "Critical"),
            ("High", "High"),
            ("Medium", "Medium"),
            ("Low", "Low"),
            ("Info", "Info"),
        )

        self.form.fields["numerical_severity"].choices = (
            ("S0", "S0"),
            ("S1", "S1"),
            ("S2", "S2"),
            ("S3", "S3"),
            ("S4", "S4"),
        )


class ApiTemplateFindingFilter(DojoFilter):
    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    class Meta:
        model = Finding_Template
        fields = ["id", "title", "cwe", "severity", "description", "mitigation"]


class FindingStatusFilter(ChoiceFilter):
    def any(self, qs, name):
        return qs.filter(
            verified=True, false_p=False, duplicate=False, out_of_scope=False
        )

    def open(self, qs, name):
        return qs.filter(
            mitigated__isnull=True,
            verified=True,
            false_p=False,
            duplicate=False,
            out_of_scope=False,
        )

    def closed(self, qs, name):
        return qs.filter(
            mitigated__isnull=False,
            verified=True,
            false_p=False,
            duplicate=False,
            out_of_scope=False,
        )

    options = {
        "": (_("Any"), any),
        0: (_("Open"), open),
        1: (_("Closed"), closed),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(FindingStatusFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        earliest_finding = get_earliest_finding(qs)
        if earliest_finding is not None:
            start_date = local_tz.localize(
                datetime.combine(earliest_finding.date, datetime.min.time())
            )
            self.start_date = _truncate(start_date - timedelta(days=1))
            self.end_date = _truncate(now() + timedelta(days=1))
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
        return self.options[value][1](self, qs, self.field_name)


class MetricsFindingFilter(FilterSet):
    start_date = DateFilter(field_name="date", label="Start Date", lookup_expr=("gt"))
    end_date = DateFilter(field_name="date", label="End Date", lookup_expr=("lt"))
    date = MetricsDateRangeFilter()
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by("name"), label="Product Type"
    )
    test__engagement__version = CharFilter(
        lookup_expr="icontains", label="Engagement Version"
    )
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    status = FindingStatusFilter(label="Status")

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    def __init__(self, *args, **kwargs):
        if args[0]:
            if args[0].get("start_date", "") != "" or args[0].get("end_date", "") != "":
                args[0]._mutable = True
                args[0]["date"] = 8
                args[0]._mutable = False
        super(MetricsFindingFilter, self).__init__(*args, **kwargs)
        self.form.fields["severity"].choices = (
            self.queryset.order_by("numerical_severity")
            .values_list("severity", "severity")
            .distinct()
        )
        if get_current_user() is not None and not get_current_user().is_staff:
            self.form.fields[
                "test__engagement__product__prod_type"
            ].queryset = Product_Type.objects.filter(
                authorized_users__in=[get_current_user()]
            )
            self.form.fields["test"].queryset = Test.objects.filter(
                Q(engagement__product__authorized_users__in=[get_current_user()])
                | Q(
                    engagement__product__prod_type__authorized_users__in=[
                        get_current_user()
                    ]
                )
            )
        # str() uses test_type
        self.form.fields["test"].queryset = self.form.fields[
            "test"
        ].queryset.prefetch_related("test_type")

    class Meta:
        model = Finding
        exclude = [
            "url",
            "description",
            "duplicate_finding",
            "mitigation",
            "unsaved_endpoints",
            "unsaved_request",
            "unsaved_response",
            "unsaved_tags",
            "references",
            "review_requested_by",
            "reviewers",
            "defect_review_requested_by",
            "thread_id",
            "notes",
            "last_reviewed_by",
            "images",
            "endpoints",
            "endpoint_status",
            "is_template",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
            "files",
        ]


class MetricsEndpointFilter(FilterSet):
    start_date = DateFilter(field_name="date", label="Start Date", lookup_expr=("gt"))
    end_date = DateFilter(field_name="date", label="End Date", lookup_expr=("lt"))
    date = MetricsDateRangeFilter()
    finding__test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all().order_by("name"), label="Product Type"
    )
    finding__test__engagement__version = CharFilter(
        lookup_expr="icontains", label="Engagement Version"
    )
    finding__severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    def __init__(self, *args, **kwargs):
        if args[0]:
            if args[0].get("start_date", "") != "" or args[0].get("end_date", "") != "":
                args[0]._mutable = True
                args[0]["date"] = 8
                args[0]._mutable = False
        super(MetricsEndpointFilter, self).__init__(*args, **kwargs)
        self.form.fields["finding__severity"].choices = (
            self.queryset.order_by("finding__numerical_severity")
            .values_list("finding__severity", "finding__severity")
            .distinct()
        )
        if get_current_user() is not None and not get_current_user().is_staff:
            self.form.fields[
                "finding__test__engagement__product__prod_type"
            ].queryset = Product_Type.objects.filter(
                authorized_users__in=[get_current_user()]
            )
            self.form.fields["endpoint"].queryset = Endpoint.objects.filter(
                Q(product__authorized_users__in=[get_current_user()])
                | Q(product__prod_type__authorized_users__in=[get_current_user()])
            )
            self.form.fields["finding"].queryset = Finding.objects.filter(
                Q(test__engagement__product__authorized_users__in=[get_current_user()])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        get_current_user()
                    ]
                )
            )

    class Meta:
        model = Endpoint_Status
        exclude = ["last_modified", "tags_from_django_tagging"]


class ProductMetricsFindingFilter(FilterSet):
    start_date = DateFilter(field_name="date", label="Start Date", lookup_expr=("gt"))
    end_date = DateFilter(field_name="date", label="End Date", lookup_expr=("lt"))
    # date = MetricsDateRangeFilter()
    test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.all().order_by("name"), label="Engagement"
    )
    test__engagement__version = CharFilter(
        lookup_expr="icontains", label="Engagement Version"
    )
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    status = FindingStatusFilter(label="Status")

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    def __init__(self, *args, **kwargs):
        # logger.debug('query before super: %s', kwargs.get('queryset', None).query)
        if args[0]:
            if args[0].get("start_date", "") != "" or args[0].get("end_date", "") != "":
                logger.debug("doing magic with args0")
                args[0]._mutable = True
                args[0]["date"] = 8
                args[0]._mutable = False
        self.pid = None
        if "pid" in kwargs:
            self.pid = kwargs.pop("pid")
        super(ProductMetricsFindingFilter, self).__init__(*args, **kwargs)
        # logger.debug('query after init: %s', self.queryset.query)
        self.form.fields["severity"].choices = (
            self.queryset.order_by("numerical_severity")
            .values_list("severity", "severity")
            .distinct()
        )

        if self.pid:
            self.form.fields["test__engagement"].queryset = Engagement.objects.filter(
                product_id=self.pid
            ).all()
            self.form.fields["test"].queryset = Test.objects.filter(
                engagement__product_id=self.pid
            ).all()

        # str() uses test_type
        self.form.fields["test"].queryset = self.form.fields[
            "test"
        ].queryset.prefetch_related("test_type")

    class Meta:
        model = Finding
        exclude = [
            "url",
            "description",
            "duplicate_finding",
            "mitigation",
            "unsaved_endpoints",
            "unsaved_request",
            "unsaved_response",
            "unsaved_tags",
            "references",
            "review_requested_by",
            "reviewers",
            "defect_review_requested_by",
            "thread_id",
            "notes",
            "last_reviewed_by",
            "images",
            "endpoints",
            "endpoint_status",
            "is_template",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
            "files",
        ]


class ProductMetricsEndpointFilter(FilterSet):
    start_date = DateFilter(field_name="date", label="Start Date", lookup_expr=("gt"))
    end_date = DateFilter(field_name="date", label="End Date", lookup_expr=("lt"))
    date = MetricsDateRangeFilter()
    finding__test__engagement = ModelMultipleChoiceFilter(
        queryset=Engagement.objects.all().order_by("name"), label="Engagement"
    )
    finding__test__engagement__version = CharFilter(
        lookup_expr="icontains", label="Engagement Version"
    )
    finding__severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)

    def __init__(self, *args, **kwargs):
        if args[0]:
            if args[0].get("start_date", "") != "" or args[0].get("end_date", "") != "":
                args[0]._mutable = True
                args[0]["date"] = 8
                args[0]._mutable = False
        super(ProductMetricsEndpointFilter, self).__init__(*args, **kwargs)
        self.form.fields["finding__severity"].choices = (
            self.queryset.order_by("finding__numerical_severity")
            .values_list("finding__severity", "finding__severity")
            .distinct()
        )

    class Meta:
        model = Endpoint_Status
        exclude = ["last_modified"]


class EndpointFilter(DojoFilter):
    product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all().order_by("name"), label="Product"
    )
    host = CharFilter(lookup_expr="icontains")
    path = CharFilter(lookup_expr="icontains")
    query = CharFilter(lookup_expr="icontains")
    fragment = CharFilter(lookup_expr="icontains")
    mitigated = CharFilter(lookup_expr="icontains")

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Endpoint.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("product", "product"),
            ("host", "host"),
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = None
        if "user" in kwargs:
            self.user = kwargs.pop("user")
        super(EndpointFilter, self).__init__(*args, **kwargs)
        if self.user and not self.user.is_staff:
            self.form.fields["product"].queryset = (
                Product.objects.filter(
                    Q(authorized_users__in=[self.user])
                    | Q(prod_type__authorized_users__in=[self.user])
                )
                .distinct()
                .order_by("name")
            )

    @property
    def qs(self):
        parent = super(EndpointFilter, self).qs
        if get_current_user() and not get_current_user().is_staff:
            return parent.filter(
                Q(product__authorized_users__in=[get_current_user()])
                | Q(product__prod_type__authorized_users__in=[get_current_user()])
            )
        else:
            return parent

    class Meta:
        model = Endpoint
        exclude = ["mitigated", "endpoint_status", "tags_from_django_tagging"]


class ApiEndpointFilter(DojoFilter):
    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    class Meta:
        model = Endpoint
        fields = ["id", "host", "product"]


class ApiTestFilter(DojoFilter):
    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    class Meta:
        model = Test
        fields = [
            "id",
            "title",
            "test_type",
            "target_start",
            "target_end",
            "notes",
            "percent_complete",
            "actual_time",
            "engagement",
            "version",
        ]


class ApiAppAnalysisFilter(DojoFilter):
    tags = CharFieldInFilter(field_name="tags__name", lookup_expr="in")

    class Meta:
        model = App_Analysis
        fields = ["product", "name", "user", "version"]


class EndpointReportFilter(DojoFilter):
    host = CharFilter(lookup_expr="icontains")
    path = CharFilter(lookup_expr="icontains")
    query = CharFilter(lookup_expr="icontains")
    fragment = CharFilter(lookup_expr="icontains")
    finding__severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    finding__mitigated = MitigatedDateRangeFilter()

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Endpoint.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    class Meta:
        model = Endpoint
        exclude = ["product", "endpoint_status", "tags_from_django_tagging"]


class ReportFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains", label="Name")
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    active = ReportBooleanFilter()
    mitigated = MitigatedDateRangeFilter()
    verified = ReportBooleanFilter()
    false_p = ReportBooleanFilter(label="False Positive")
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted"
    )
    # queryset will be restricted in __init__, here we don't have access to the logged in user
    duplicate = ReportBooleanFilter()
    duplicate_finding = ModelChoiceFilter(
        queryset=Finding.objects.filter(original_finding__isnull=False).distinct()
    )
    out_of_scope = ReportBooleanFilter()

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    class Meta:
        model = Finding
        # exclude sonarqube issue as by default it will show all without checking permissions
        exclude = [
            "date",
            "cwe",
            "url",
            "description",
            "mitigation",
            "impact",
            "endpoint",
            "references",
            "test",
            "is_template",
            "sonarqube_issue" "thread_id",
            "notes",
            "endpoints",
            "endpoint_status",
            "numerical_severity",
            "reporter",
            "last_reviewed",
            "images",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
        ]

    def __init__(self, *args, **kwargs):
        self.prod_type = None
        self.product = None
        self.engagement = None
        self.test = None
        if "prod_type" in kwargs:
            self.prod_type = kwargs.pop("prod_type")
        if "product" in kwargs:
            self.product = kwargs.pop("product")
        if "engagement" in kwargs:
            self.engagement = kwargs.pop("engagement")
        if "test" in kwargs:
            self.test = kwargs.pop("test")

        super().__init__(*args, **kwargs)
        # duplicate_finding queryset needs to restricted in line with permissions
        # and inline with report scope to avoid a dropdown with 100K entries
        duplicate_finding_query_set = self.form.fields["duplicate_finding"].queryset
        if get_current_user() is not None and not get_current_user().is_staff:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(
                Q(test__engagement__product__authorized_users__in=[get_current_user()])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        get_current_user()
                    ]
                )
            )

        if self.test:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(
                test=self.test
            )
            del self.form.fields["test__tags"]
            del self.form.fields["test__engagement__tags"]
            del self.form.fields["test__engagement__product__tags"]
        if self.engagement:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(
                test__engagement=self.engagement
            )
            del self.form.fields["test__engagement__tags"]
            del self.form.fields["test__engagement__product__tags"]
        elif self.product:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(
                test__engagement__product=self.product
            )
            del self.form.fields["test__engagement__product__tags"]
        elif self.prod_type:
            duplicate_finding_query_set = duplicate_finding_query_set.filter(
                test__engagement__product__prod_type=self.prod_type
            )

        self.form.fields["duplicate_finding"].queryset = duplicate_finding_query_set


class ReportAuthedFindingFilter(DojoFilter):
    title = CharFilter(lookup_expr="icontains", label="Name")
    test__engagement__product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Product"
    )
    test__engagement__product__prod_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(), label="Product Type"
    )
    severity = MultipleChoiceFilter(choices=SEVERITY_CHOICES)
    active = ReportBooleanFilter()
    mitigated = MitigatedDateRangeFilter()
    verified = ReportBooleanFilter()
    false_p = ReportBooleanFilter(label="False Positive")
    test__engagement__risk_acceptance = ReportRiskAcceptanceFilter(
        label="Risk Accepted"
    )
    duplicate = ReportBooleanFilter()
    duplicate_finding = ModelChoiceFilter(
        queryset=Finding.objects.filter(original_finding__isnull=False).distinct()
    )
    out_of_scope = ReportBooleanFilter()

    tags = ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Finding.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__tags = ModelMultipleChoiceFilter(
        field_name="test__tags__name",
        to_field_name="name",
        queryset=Test.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__tags__name",
        to_field_name="name",
        queryset=Engagement.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    test__engagement__product__tags = ModelMultipleChoiceFilter(
        field_name="test__engagement__product__tags__name",
        to_field_name="name",
        queryset=Product.tags.tag_model.objects.all().order_by("name"),
        # label='tags', # doesn't work with tagulous, need to set in __init__ below
    )

    tag = CharFilter(
        field_name="tags__name", lookup_expr="icontains", label="Tag name contains"
    )

    def __init__(self, *args, **kwargs):
        super(ReportAuthedFindingFilter, self).__init__(*args, **kwargs)
        if get_current_user() and not get_current_user().is_staff:
            self.form.fields[
                "test__engagement__product"
            ].queryset = Product.objects.filter(
                Q(authorized_users__in=[get_current_user()])
                | Q(prod_type__authorized_users__in=[get_current_user()])
            )
            self.form.fields[
                "test__engagement__product__prod_type"
            ].queryset = Product_Type.objects.filter(
                authorized_users__in=[get_current_user()]
            )
            self.form.fields["duplicate_finding"].queryset = Finding.objects.filter(
                Q(test__engagement__product__authorized_users__in=[get_current_user()])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        get_current_user()
                    ]
                )
            )

    @property
    def qs(self):
        parent = super(ReportAuthedFindingFilter, self).qs
        if get_current_user() and not get_current_user().is_staff:
            return parent.filter(
                Q(test__engagement__product__authorized_users__in=[get_current_user()])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        get_current_user()
                    ]
                )
            )
        else:
            return parent

    class Meta:
        model = Finding
        exclude = [
            "date",
            "cwe",
            "url",
            "description",
            "mitigation",
            "impact",
            "endpoint",
            "references",
            "test",
            "is_template",
            "thread_id",
            "notes",
            "endpoints",
            "endpoint_status",
            "numerical_severity",
            "reporter",
            "last_reviewed",
            "jira_creation",
            "jira_change",
            "tags_from_django_tagging",
        ]


class UserFilter(DojoFilter):
    first_name = CharFilter(lookup_expr="icontains")
    last_name = CharFilter(lookup_expr="icontains")
    username = CharFilter(lookup_expr="icontains")
    product_type = ModelMultipleChoiceFilter(
        queryset=Product_Type.objects.all(), label="Authorized Product Type"
    )
    product = ModelMultipleChoiceFilter(
        queryset=Product.objects.all(), label="Authorized Product"
    )

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("username", "username"),
            ("last_name", "last_name"),
            ("first_name", "first_name"),
            ("email", "email"),
            ("is_active", "is_active"),
            ("is_staff", "is_staff"),
            ("is_superuser", "is_superuser"),
        ),
        field_labels={
            "username": "User Name",
            "is_active": "Active",
            "is_staff": "Staff",
            "is_superuser": "Superuser",
        },
    )

    class Meta:
        model = Dojo_User
        fields = [
            "is_staff",
            "is_superuser",
            "is_active",
            "first_name",
            "last_name",
            "username",
        ]
        exclude = [
            "password",
            "last_login",
            "groups",
            "user_permissions",
            "date_joined",
        ]


class ReportFilter(DojoFilter):
    name = CharFilter(lookup_expr="icontains")
    type = MultipleChoiceFilter(choices=[])
    format = MultipleChoiceFilter(choices=[])
    requester = ModelMultipleChoiceFilter(queryset=Dojo_User.objects.all())
    datetime = DateTimeFilter()
    status = MultipleChoiceFilter(choices=[])

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("datetime", "datetime"),
            ("name", "name"),
            ("type", "type"),
            ("format", "format"),
            ("requester", "requester"),
        ),
        field_labels={
            "datetime": "Date",
        },
    )

    class Meta:
        model = Report
        exclude = ["task_id", "file"]

    def __init__(self, *args, **kwargs):
        super(ReportFilter, self).__init__(*args, **kwargs)
        type = dict()
        type = dict(
            [report.type, report.type]
            for report in self.queryset.distinct()
            if report.type is not None
        )
        type = collections.OrderedDict(sorted(type.items()))
        self.form.fields["type"].choices = list(type.items())

        status = dict()
        status = dict(
            [report.status, report.status]
            for report in self.queryset.distinct()
            if report.status is not None
        )
        status = collections.OrderedDict(sorted(status.items()))
        self.form.fields["status"].choices = list(status.items())


class EngineerFilter(DojoFilter):
    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("username", "username"),
            ("last_name", "last_name"),
            ("first_name", "first_name"),
            ("email", "email"),
            ("is_active", "is_active"),
            ("is_staff", "is_staff"),
            ("is_superuser", "is_superuser"),
        ),
        field_labels={
            "username": "User Name",
            "is_active": "Active",
            "is_staff": "Staff",
            "is_superuser": "Superuser",
        },
    )

    class Meta:
        model = Dojo_User
        fields = [
            "is_staff",
            "is_superuser",
            "is_active",
            "username",
            "email",
            "last_name",
            "first_name",
        ]
        exclude = [
            "password",
            "last_login",
            "groups",
            "user_permissions",
            "date_joined",
        ]


class LogEntryFilter(DojoFilter):
    from auditlog.models import LogEntry

    action = MultipleChoiceFilter(choices=LogEntry.Action.choices)
    actor = ModelMultipleChoiceFilter(queryset=Dojo_User.objects.all())
    timestamp = DateRangeFilter()

    class Meta:
        model = LogEntry
        exclude = [
            "content_type",
            "object_pk",
            "object_id",
            "object_repr",
            "changes",
            "additional_data",
        ]


class ProductTypeFilter(DojoFilter):
    name = CharFilter(lookup_expr="icontains")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(("name", "name"),),
    )

    class Meta:
        model = Product_Type
        exclude = []
        include = ("name",)


class TestTypeFilter(DojoFilter):
    name = CharFilter(lookup_expr="icontains")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(("name", "name"),),
    )

    class Meta:
        model = Test_Type
        exclude = []
        include = ("name",)


class DevelopmentEnvironmentFilter(DojoFilter):
    name = CharFilter(lookup_expr="icontains")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(("name", "name"),),
    )

    class Meta:
        model = Development_Environment
        exclude = []
        include = ("name",)


class NoteTypesFilter(DojoFilter):
    name = CharFilter(lookup_expr="icontains")

    o = OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ("name", "name"),
            ("description", "description"),
            ("is_single", "is_single"),
            ("is_mandatory", "is_mandatory"),
        ),
    )

    class Meta:
        model = Note_Type
        exclude = []
        include = ("name", "is_single", "description")


# ==============================
# Defect Dojo Engaegment Surveys
# ==============================


class QuestionnaireFilter(FilterSet):
    name = CharFilter(lookup_expr="icontains")
    description = CharFilter(lookup_expr="icontains")
    active = BooleanFilter()

    class Meta:
        model = Engagement_Survey
        exclude = ["questions"]

    survey_set = FilterSet


class QuestionTypeFilter(ChoiceFilter):
    def any(self, qs, name):
        return qs.all()

    def text_question(self, qs, name):
        return qs.filter(
            polymorphic_ctype=ContentType.objects.get_for_model(TextQuestion)
        )

    def choice_question(self, qs, name):
        return qs.filter(
            polymorphic_ctype=ContentType.objects.get_for_model(ChoiceQuestion)
        )

    options = {
        "": (_("Any"), any),
        1: (_("Text Question"), text_question),
        2: (_("Choice Question"), choice_question),
    }

    def __init__(self, *args, **kwargs):
        kwargs["choices"] = [
            (key, value[0]) for key, value in six.iteritems(self.options)
        ]
        super(QuestionTypeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ""
        return self.options[value][1](self, qs, self.options[value][0])


class QuestionFilter(FilterSet):
    text = CharFilter(lookup_expr="icontains")
    type = QuestionTypeFilter()

    class Meta:
        model = Question
        exclude = ["polymorphic_ctype", "created", "modified", "order"]

    question_set = FilterSet
