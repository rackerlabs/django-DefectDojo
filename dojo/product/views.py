# #  product
import calendar as tcalendar
import logging
import base64
from collections import OrderedDict
from datetime import datetime, date, timedelta
from math import ceil
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count, Q, Max
from django.contrib.admin.utils import NestedObjects
from django.db import DEFAULT_DB_ALIAS, connection
from dojo.templatetags.display_tags import get_level
from dojo.filters import (
    ProductFilter,
    EngagementFilter,
    ProductMetricsEndpointFilter,
    ProductMetricsFindingFilter,
    ProductComponentFilter,
)
from dojo.forms import (
    ProductForm,
    EngForm,
    DeleteProductForm,
    DojoMetaDataForm,
    JIRAProjectForm,
    JIRAFindingForm,
    AdHocFindingForm,
    EngagementPresetsForm,
    DeleteEngagementPresetsForm,
    Sonarqube_ProductForm,
    ProductNotificationsForm,
    GITHUB_Product_Form,
    GITHUBFindingForm,
    App_AnalysisTypeForm,
    JIRAEngagementForm,
)
from dojo.models import (
    Product_Type,
    Note_Type,
    Finding,
    Product,
    Engagement,
    ScanSettings,
    Test,
    GITHUB_PKey,
    Finding_Template,
    Test_Type,
    System_Settings,
    Languages,
    App_Analysis,
    Benchmark_Type,
    Benchmark_Product_Summary,
    Endpoint_Status,
    Endpoint,
    Engagement_Presets,
    DojoMeta,
    Sonarqube_Product,
    Notifications,
    BurpRawRequestResponse,
)

from dojo.utils import (
    get_page_items,
    add_breadcrumb,
    get_system_setting,
    Product_Tab,
    get_punchcard_data,
    queryset_check,
)

from dojo.notifications.helper import create_notification
from django.db.models import Prefetch, F
from django.db.models.query import QuerySet
from github import Github
from dojo.user.helper import (
    user_must_be_authorized,
    user_is_authorized,
    check_auth_users_list,
)
from django.contrib.postgres.aggregates import StringAgg
from dojo.components.sql_group_concat import Sql_GroupConcat
import dojo.jira_link.helper as jira_helper
import dojo.finding.helper as finding_helper

logger = logging.getLogger(__name__)


def product(request):
    # validate prod_type param
    product_type = None
    if "prod_type" in request.GET:
        p = request.GET.getlist("prod_type", [])
        if len(p) == 1:
            product_type = get_object_or_404(Product_Type, id=p[0])

    prods = Product.objects.all()

    if not request.user.is_staff:
        prods = prods.filter(
            Q(authorized_users__in=[request.user])
            | Q(prod_type__authorized_users__in=[request.user])
        )

    # perform all stuff for filtering and pagination first, before annotation/prefetching
    # otherwise the paginator will perform all the annotations/prefetching already only to count the total number of records
    # see https://code.djangoproject.com/ticket/23771 and https://code.djangoproject.com/ticket/25375
    name_words = prods.values_list("name", flat=True)

    prod_filter = ProductFilter(request.GET, queryset=prods, user=request.user)

    prod_list = get_page_items(request, prod_filter.qs, 25)

    # perform annotation/prefetching by replacing the queryset in the page with an annotated/prefetched queryset.
    prod_list.object_list = prefetch_for_product(prod_list.object_list)

    add_breadcrumb(
        title="Product List", top_level=not len(request.GET), request=request
    )
    return render(
        request,
        "dojo/product.html",
        {
            "prod_list": prod_list,
            "prod_filter": prod_filter,
            "name_words": sorted(set(name_words)),
            "user": request.user,
        },
    )


def prefetch_for_product(prods):
    prefetched_prods = prods
    if isinstance(
        prods, QuerySet
    ):  # old code can arrive here with prods being a list because the query was already executed
        prefetched_prods = (
            prefetched_prods.select_related("technical_contact")
            .select_related("product_manager")
            .select_related("prod_type")
            .select_related("team_manager")
        )
        prefetched_prods = prefetched_prods.annotate(
            active_engagement_count=Count(
                "engagement__id", filter=Q(engagement__active=True)
            )
        )
        prefetched_prods = prefetched_prods.annotate(
            closed_engagement_count=Count(
                "engagement__id", filter=Q(engagement__active=False)
            )
        )
        prefetched_prods = prefetched_prods.annotate(
            last_engagement_date=Max("engagement__target_start")
        )
        prefetched_prods = prefetched_prods.annotate(
            active_finding_count=Count(
                "engagement__test__finding__id",
                filter=Q(engagement__test__finding__active=True),
            )
        )
        prefetched_prods = prefetched_prods.prefetch_related(
            "jira_project_set__jira_instance"
        )
        prefetched_prods = prefetched_prods.prefetch_related(
            Prefetch(
                "github_pkey_set",
                queryset=GITHUB_PKey.objects.all().select_related("git_conf"),
                to_attr="github_confs",
            )
        )
        active_endpoint_query = Endpoint.objects.filter(
            finding__active=True, finding__mitigated__isnull=True
        )
        prefetched_prods = prefetched_prods.prefetch_related(
            Prefetch(
                "endpoint_set",
                queryset=active_endpoint_query,
                to_attr="active_endpoints",
            )
        )
        prefetched_prods = prefetched_prods.prefetch_related("tags")

    else:
        logger.debug("unable to prefetch because query was already executed")

    return prefetched_prods


def iso_to_gregorian(iso_year, iso_week, iso_day):
    jan4 = date(iso_year, 1, 4)
    start = jan4 - timedelta(days=jan4.isoweekday() - 1)
    return start + timedelta(weeks=iso_week - 1, days=iso_day - 1)


@user_must_be_authorized(Product, "view", "pid")
def view_product(request, pid):
    prod_query = (
        Product.objects.all()
        .select_related("product_manager", "technical_contact", "team_manager")
        .prefetch_related("authorized_users")
    )
    prod = get_object_or_404(prod_query, id=pid)
    personal_notifications_form = ProductNotificationsForm(
        instance=Notifications.objects.filter(user=request.user)
        .filter(product=prod)
        .first()
    )
    langSummary = Languages.objects.filter(product=prod).aggregate(
        Sum("files"), Sum("code"), Count("files")
    )
    languages = Languages.objects.filter(product=prod).order_by("-code")
    app_analysis = App_Analysis.objects.filter(product=prod).order_by("name")
    benchmark_type = Benchmark_Type.objects.filter(enabled=True).order_by("name")
    benchmarks = Benchmark_Product_Summary.objects.filter(
        product=prod, publish=True, benchmark_type__enabled=True
    ).order_by("benchmark_type__name")
    benchAndPercent = []
    for i in range(0, len(benchmarks)):
        benchAndPercent.append([benchmarks[i].benchmark_type, get_level(benchmarks[i])])

    system_settings = System_Settings.objects.get()

    product_metadata = dict(
        prod.product_meta.order_by("name").values_list("name", "value")
    )

    open_findings = (
        Finding.objects.filter(
            test__engagement__product=prod,
            false_p=False,
            active=True,
            duplicate=False,
            out_of_scope=False,
        )
        .order_by("numerical_severity")
        .values("severity")
        .annotate(count=Count("severity"))
    )

    critical = 0
    high = 0
    medium = 0
    low = 0
    info = 0

    for v in open_findings:
        if v["severity"] == "Critical":
            critical = v["count"]
        elif v["severity"] == "High":
            high = v["count"]
        elif v["severity"] == "Medium":
            medium = v["count"]
        elif v["severity"] == "Low":
            low = v["count"]
        elif v["severity"] == "Info":
            info = v["count"]

    total = critical + high + medium + low + info

    product_tab = Product_Tab(pid, title="Product", tab="overview")
    return render(
        request,
        "dojo/view_product_details.html",
        {
            "prod": prod,
            "product_tab": product_tab,
            "product_metadata": product_metadata,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "info": info,
            "total": total,
            "user": request.user,
            "languages": languages,
            "langSummary": langSummary,
            "app_analysis": app_analysis,
            "system_settings": system_settings,
            "benchmarks_percents": benchAndPercent,
            "benchmarks": benchmarks,
            "personal_notifications_form": personal_notifications_form,
        },
    )


def view_product_components(request, pid):
    prod = get_object_or_404(Product, id=pid)
    product_tab = Product_Tab(pid, title="Product", tab="components")
    separator = ", "

    # Get components ordered by component_name and concat component versions to the same row
    if connection.vendor == "postgresql":
        component_query = (
            Finding.objects.filter(test__engagement__product__id=pid)
            .values("component_name")
            .order_by("component_name")
            .annotate(
                component_version=StringAgg(
                    "component_version", delimiter=separator, distinct=True
                )
            )
        )
    else:
        component_query = Finding.objects.filter(
            test__engagement__product__id=pid
        ).values("component_name")
        component_query = component_query.annotate(
            component_version=Sql_GroupConcat(
                "component_version", separator=separator, distinct=True
            )
        )

    # Append finding counts
    component_query = component_query.annotate(total=Count("id")).order_by(
        "component_name", "component_version"
    )
    component_query = component_query.annotate(
        actives=Count("id", filter=Q(active=True))
    )
    component_query = component_query.annotate(
        duplicate=(Count("id", filter=Q(duplicate=True)))
    )

    # Default sort by total descending
    component_query = component_query.order_by("-total")

    comp_filter = ProductComponentFilter(request.GET, queryset=component_query)
    result = get_page_items(request, comp_filter.qs, 25)

    # Filter out None values for auto-complete
    component_words = component_query.exclude(component_name__isnull=True).values_list(
        "component_name", flat=True
    )

    return render(
        request,
        "dojo/product_components.html",
        {
            "prod": prod,
            "filter": comp_filter,
            "product_tab": product_tab,
            "result": result,
            "component_words": sorted(set(component_words)),
        },
    )


def identify_view(request):
    get_data = request.GET
    view = get_data.get("type", None)
    if view:
        # value of view is reflected in the template, make sure it's valid
        # although any XSS should be catch by django autoescape, we see people sometimes using '|safe'...
        if view in ["Endpoint", "Finding"]:
            return view
        raise ValueError('invalid view, view must be "Endpoint" or "Finding"')
    else:
        if get_data.get("finding__severity", None):
            return "Endpoint"
        elif get_data.get("false_positive", None):
            return "Endpoint"
    referer = request.META.get("HTTP_REFERER", None)
    if referer:
        if referer.find("type=Endpoint") > -1:
            return "Endpoint"
    return "Finding"


def finding_querys(request, prod):
    filters = dict()

    findings_query = Finding.objects.filter(
        test__engagement__product=prod,
        severity__in=("Critical", "High", "Medium", "Low", "Info"),
    )

    # prefetch only what's needed to avoid lots of repeated queries
    findings_query = findings_query.prefetch_related(
        # 'test__engagement',
        # 'test__engagement__risk_acceptance',
        # 'found_by',
        # 'test',
        # 'test__test_type',
        # 'risk_acceptance_set',
        "reporter"
    )
    findings = ProductMetricsFindingFilter(
        request.GET, queryset=findings_query, pid=prod
    )
    findings_qs = queryset_check(findings)
    filters["form"] = findings.form

    # dead code:
    # if not findings_qs and not findings_query:
    #     # logger.debug('all filtered')
    #     findings = findings_query
    #     findings_qs = queryset_check(findings)
    #     messages.add_message(request,
    #                                  messages.ERROR,
    #                                  'All objects have been filtered away. Displaying all objects',
    #                                  extra_tags='alert-danger')

    try:
        # logger.debug(findings_qs.query)
        start_date = findings_qs.earliest("date").date
        start_date = datetime(
            start_date.year,
            start_date.month,
            start_date.day,
            tzinfo=timezone.get_current_timezone(),
        )
        end_date = findings_qs.latest("date").date
        end_date = datetime(
            end_date.year,
            end_date.month,
            end_date.day,
            tzinfo=timezone.get_current_timezone(),
        )
    except Exception as e:
        logger.debug(e)
        start_date = timezone.now()
        end_date = timezone.now()
    week = end_date - timedelta(days=7)  # seven days and /newnewer are considered "new"

    # risk_acceptances = Risk_Acceptance.objects.filter(engagement__in=Engagement.objects.filter(product=prod)).prefetch_related('accepted_findings')
    # filters['accepted'] = [finding for ra in risk_acceptances for finding in ra.accepted_findings.all()]

    from dojo.finding.views import ACCEPTED_FINDINGS_QUERY

    filters["accepted"] = (
        Finding.objects.filter(test__engagement__product=prod)
        .filter(ACCEPTED_FINDINGS_QUERY)
        .distinct()
    )

    filters["verified"] = findings_qs.filter(
        date__range=[start_date, end_date],
        false_p=False,
        active=True,
        verified=True,
        duplicate=False,
        out_of_scope=False,
    ).order_by("date")
    filters["new_verified"] = findings_qs.filter(
        date__range=[week, end_date],
        false_p=False,
        verified=True,
        active=True,
        duplicate=False,
        out_of_scope=False,
    ).order_by("date")
    filters["open"] = findings_qs.filter(
        date__range=[start_date, end_date],
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        active=True,
        is_Mitigated=False,
    )
    filters["inactive"] = findings_qs.filter(
        date__range=[start_date, end_date],
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        active=False,
        is_Mitigated=False,
    )
    filters["closed"] = findings_qs.filter(
        date__range=[start_date, end_date],
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        active=False,
        is_Mitigated=True,
    )
    filters["false_positive"] = findings_qs.filter(
        date__range=[start_date, end_date],
        false_p=True,
        duplicate=False,
        out_of_scope=False,
    )
    filters["out_of_scope"] = findings_qs.filter(
        date__range=[start_date, end_date],
        false_p=False,
        duplicate=False,
        out_of_scope=True,
    )
    filters["all"] = findings_qs
    filters["open_vulns"] = (
        findings_qs.filter(
            false_p=False,
            duplicate=False,
            out_of_scope=False,
            active=True,
            mitigated__isnull=True,
            cwe__isnull=False,
        )
        .order_by("cwe")
        .values("cwe")
        .annotate(count=Count("cwe"))
    )

    filters["all_vulns"] = (
        findings_qs.filter(
            duplicate=False,
            cwe__isnull=False,
        )
        .order_by("cwe")
        .values("cwe")
        .annotate(count=Count("cwe"))
    )

    filters["start_date"] = start_date
    filters["end_date"] = end_date
    filters["week"] = week

    return filters


def endpoint_querys(request, prod):
    filters = dict()
    endpoints_query = (
        Endpoint_Status.objects.filter(
            finding__test__engagement__product=prod,
            finding__severity__in=("Critical", "High", "Medium", "Low", "Info"),
        )
        .prefetch_related(
            "finding__test__engagement",
            "finding__test__engagement__risk_acceptance",
            "finding__risk_acceptance_set",
            "finding__reporter",
        )
        .annotate(severity=F("finding__severity"))
    )
    endpoints = ProductMetricsEndpointFilter(request.GET, queryset=endpoints_query)
    endpoints_qs = queryset_check(endpoints)
    filters["form"] = endpoints.form

    if not endpoints_qs and not endpoints_query:
        endpoints = endpoints_query
        endpoints_qs = queryset_check(endpoints)
        messages.add_message(
            request,
            messages.ERROR,
            "All objects have been filtered away. Displaying all objects",
            extra_tags="alert-danger",
        )

    try:
        start_date = endpoints_qs.earliest("date").date
        start_date = datetime(
            start_date.year,
            start_date.month,
            start_date.day,
            tzinfo=timezone.get_current_timezone(),
        )
        end_date = endpoints_qs.latest("date").date
        end_date = datetime(
            end_date.year,
            end_date.month,
            end_date.day,
            tzinfo=timezone.get_current_timezone(),
        )
    except:
        start_date = timezone.now()
        end_date = timezone.now()
    week = end_date - timedelta(days=7)  # seven days and /newnewer are considered "new"

    filters["accepted"] = endpoints_qs.filter(
        date__range=[start_date, end_date], risk_accepted=True
    ).order_by("date")
    filters["verified"] = endpoints_qs.filter(
        date__range=[start_date, end_date],
        false_positive=False,
        mitigated=True,
        out_of_scope=False,
    ).order_by("date")
    filters["new_verified"] = endpoints_qs.filter(
        date__range=[week, end_date],
        false_positive=False,
        mitigated=True,
        out_of_scope=False,
    ).order_by("date")
    filters["open"] = endpoints_qs.filter(
        date__range=[start_date, end_date], mitigated=False
    )
    filters["inactive"] = endpoints_qs.filter(
        date__range=[start_date, end_date], mitigated=True
    )
    filters["closed"] = endpoints_qs.filter(
        date__range=[start_date, end_date], mitigated=True
    )
    filters["false_positive"] = endpoints_qs.filter(
        date__range=[start_date, end_date], false_positive=True
    )
    filters["out_of_scope"] = endpoints_qs.filter(
        date__range=[start_date, end_date], out_of_scope=True
    )
    filters["all"] = endpoints_qs
    filters["open_vulns"] = (
        endpoints_qs.filter(
            false_positive=False,
            out_of_scope=False,
            mitigated=True,
            finding__cwe__isnull=False,
        )
        .order_by("finding__cwe")
        .values("finding__cwe")
        .annotate(count=Count("finding__cwe"))
    )

    filters["all_vulns"] = (
        endpoints_qs.filter(
            finding__cwe__isnull=False,
        )
        .order_by("finding__cwe")
        .values("finding__cwe")
        .annotate(count=Count("finding__cwe"))
    )

    filters["start_date"] = start_date
    filters["end_date"] = end_date
    filters["week"] = week

    return filters


@user_must_be_authorized(Product, "view", "pid")
def view_product_metrics(request, pid):
    prod = get_object_or_404(Product, id=pid)
    engs = Engagement.objects.filter(product=prod, active=True)
    view = identify_view(request)

    result = EngagementFilter(
        request.GET,
        queryset=Engagement.objects.filter(product=prod, active=False).order_by(
            "-target_end"
        ),
    )

    i_engs_page = get_page_items(request, result.qs, 10)

    scan_sets = ScanSettings.objects.filter(product=prod)

    filters = dict()
    if view == "Finding":
        filters = finding_querys(request, prod)
    elif view == "Endpoint":
        filters = endpoint_querys(request, prod)

    start_date = filters["start_date"]
    end_date = filters["end_date"]
    week_date = filters["week"]

    tests = Test.objects.filter(engagement__product=prod).prefetch_related(
        "finding_set", "test_type"
    )
    tests = tests.annotate(
        verified_finding_count=Count("finding__id", filter=Q(finding__verified=True))
    )

    open_vulnerabilities = filters["open_vulns"]
    all_vulnerabilities = filters["all_vulns"]

    start_date = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    r = relativedelta(end_date, start_date)
    weeks_between = int(ceil((((r.years * 12) + r.months) * 4.33) + (r.days / 7)))
    if weeks_between <= 0:
        weeks_between += 2

    punchcard, ticks = get_punchcard_data(
        filters.get("open", None), start_date, weeks_between, view
    )

    add_breadcrumb(parent=prod, top_level=False, request=request)

    open_close_weekly = OrderedDict()
    new_weekly = OrderedDict()
    severity_weekly = OrderedDict()
    critical_weekly = OrderedDict()
    high_weekly = OrderedDict()
    medium_weekly = OrderedDict()

    for v in filters.get("open", None):
        iso_cal = v.date.isocalendar()
        x = iso_to_gregorian(iso_cal[0], iso_cal[1], 1)
        y = x.strftime("<span class='small'>%m/%d<br/>%Y</span>")
        x = tcalendar.timegm(x.timetuple()) * 1000
        if x not in critical_weekly:
            critical_weekly[x] = {"count": 0, "week": y}
        if x not in high_weekly:
            high_weekly[x] = {"count": 0, "week": y}
        if x not in medium_weekly:
            medium_weekly[x] = {"count": 0, "week": y}

        if x in open_close_weekly:
            if v.mitigated:
                open_close_weekly[x]["closed"] += 1
            else:
                open_close_weekly[x]["open"] += 1
        else:
            if v.mitigated:
                open_close_weekly[x] = {"closed": 1, "open": 0, "accepted": 0}
            else:
                open_close_weekly[x] = {"closed": 0, "open": 1, "accepted": 0}
            open_close_weekly[x]["week"] = y

        if view == "Finding":
            severity = v.severity
        elif view == "Endpoint":
            severity = v.finding.severity

        if x in severity_weekly:
            if severity in severity_weekly[x]:
                severity_weekly[x][severity] += 1
            else:
                severity_weekly[x][severity] = 1
        else:
            severity_weekly[x] = {
                "Critical": 0,
                "High": 0,
                "Medium": 0,
                "Low": 0,
                "Info": 0,
            }
            severity_weekly[x][severity] = 1
            severity_weekly[x]["week"] = y

        if severity == "Critical":
            if x in critical_weekly:
                critical_weekly[x]["count"] += 1
            else:
                critical_weekly[x] = {"count": 1, "week": y}
        elif severity == "High":
            if x in high_weekly:
                high_weekly[x]["count"] += 1
            else:
                high_weekly[x] = {"count": 1, "week": y}
        elif severity == "Medium":
            if x in medium_weekly:
                medium_weekly[x]["count"] += 1
            else:
                medium_weekly[x] = {"count": 1, "week": y}

    for a in filters.get("accepted", None):
        if view == "Finding":
            finding = a
        elif view == "Endpoint":
            finding = v.finding
        iso_cal = a.date.isocalendar()
        x = iso_to_gregorian(iso_cal[0], iso_cal[1], 1)
        y = x.strftime("<span class='small'>%m/%d<br/>%Y</span>")
        x = tcalendar.timegm(x.timetuple()) * 1000

        if x in open_close_weekly:
            open_close_weekly[x]["accepted"] += 1
        else:
            open_close_weekly[x] = {"closed": 0, "open": 0, "accepted": 1}
            open_close_weekly[x]["week"] = y

    test_data = {}
    for t in tests:
        if t.test_type.name in test_data:
            test_data[t.test_type.name] += t.verified_finding_count
        else:
            test_data[t.test_type.name] = t.verified_finding_count
    product_tab = Product_Tab(pid, title="Product", tab="metrics")

    return render(
        request,
        "dojo/product_metrics.html",
        {
            "prod": prod,
            "product_tab": product_tab,
            "engs": engs,
            "i_engs": i_engs_page,
            "scan_sets": scan_sets,
            "view": view,
            "verified_objs": filters.get("verified", None),
            "open_objs": filters.get("open", None),
            "inactive_objs": filters.get("inactive", None),
            "closed_objs": filters.get("closed", None),
            "false_positive_objs": filters.get("false_positive", None),
            "out_of_scope_objs": filters.get("out_of_scope", None),
            "accepted_objs": filters.get("accepted", None),
            "new_objs": filters.get("new_verified", None),
            "all_objs": filters.get("all", None),
            "form": filters.get("form", None),
            "reset_link": reverse("view_product_metrics", args=(prod.id,))
            + "?type="
            + view,
            "open_vulnerabilities": open_vulnerabilities,
            "all_vulnerabilities": all_vulnerabilities,
            "start_date": start_date,
            "punchcard": punchcard,
            "ticks": ticks,
            "open_close_weekly": open_close_weekly,
            "severity_weekly": severity_weekly,
            "critical_weekly": critical_weekly,
            "high_weekly": high_weekly,
            "medium_weekly": medium_weekly,
            "test_data": test_data,
            "user": request.user,
        },
    )


def view_engagements(request, pid, engagement_type="Interactive"):
    prod = get_object_or_404(Product, id=pid)
    auth = request.user.is_staff or check_auth_users_list(request.user, prod)
    if not auth:
        raise PermissionDenied

    default_page_num = 10

    # In Progress Engagements
    engs = Engagement.objects.filter(
        product=prod, active=True, status="In Progress", engagement_type=engagement_type
    ).order_by("-updated")
    active_engs = EngagementFilter(request.GET, queryset=engs)
    result_active_engs = get_page_items(
        request, active_engs.qs, default_page_num, param_name="engs"
    )
    # prefetch only after creating the filters to avoid https://code.djangoproject.com/ticket/23771 and https://code.djangoproject.com/ticket/25375
    result_active_engs.object_list = prefetch_for_view_engagements(
        result_active_engs.object_list
    )

    # Engagements that are queued because they haven't started or paused
    engs = Engagement.objects.filter(
        ~Q(status="In Progress"),
        product=prod,
        active=True,
        engagement_type=engagement_type,
    ).order_by("-updated")
    queued_engs = EngagementFilter(request.GET, queryset=engs)
    result_queued_engs = get_page_items(
        request, queued_engs.qs, default_page_num, param_name="queued_engs"
    )
    result_queued_engs.object_list = prefetch_for_view_engagements(
        result_queued_engs.object_list
    )

    # Cancelled or Completed Engagements
    engs = Engagement.objects.filter(
        product=prod, active=False, engagement_type=engagement_type
    ).order_by("-target_end")
    result_inactive = EngagementFilter(request.GET, queryset=engs)
    result_inactive_engs_page = get_page_items(
        request, result_inactive.qs, default_page_num, param_name="i_engs"
    )
    result_inactive_engs_page.object_list = prefetch_for_view_engagements(
        result_inactive_engs_page.object_list
    )

    title = "All Engagements"
    if engagement_type == "CI/CD":
        title = "CI/CD Engagements"

    product_tab = Product_Tab(pid, title=title, tab="engagements")
    return render(
        request,
        "dojo/view_engagements.html",
        {
            "prod": prod,
            "product_tab": product_tab,
            "engagement_type": engagement_type,
            "engs": result_active_engs,
            "engs_count": result_active_engs.paginator.count,
            "queued_engs": result_queued_engs,
            "queued_engs_count": result_queued_engs.paginator.count,
            "i_engs": result_inactive_engs_page,
            "i_engs_count": result_inactive_engs_page.paginator.count,
            "user": request.user,
            "authorized": auth,
        },
    )


def prefetch_for_view_engagements(engs):
    prefetched_engs = engs
    if isinstance(
        engs, QuerySet
    ):  # old code can arrive here with prods being a list because the query was already executed
        prefetched_engs = prefetched_engs.select_related("lead")
        prefetched_engs = prefetched_engs.prefetch_related("test_set")
        prefetched_engs = prefetched_engs.prefetch_related(
            "test_set__test_type"
        )  # test.name uses test_type
        prefetched_engs = prefetched_engs.annotate(
            count_findings_all=Count("test__finding__id")
        )
        prefetched_engs = prefetched_engs.annotate(
            count_findings_open=Count(
                "test__finding__id", filter=Q(test__finding__active=True)
            )
        )
        prefetched_engs = prefetched_engs.annotate(
            count_findings_open_verified=Count(
                "test__finding__id",
                filter=Q(test__finding__active=True) & Q(test__finding__verified=True),
            )
        )
        prefetched_engs = prefetched_engs.annotate(
            count_findings_close=Count(
                "test__finding__id", filter=Q(test__finding__is_Mitigated=True)
            )
        )
        prefetched_engs = prefetched_engs.annotate(
            count_findings_duplicate=Count(
                "test__finding__id", filter=Q(test__finding__duplicate=True)
            )
        )
        ACCEPTED_FINDINGS_QUERY = Q(test__finding__risk_accepted=True)
        prefetched_engs = prefetched_engs.annotate(
            count_findings_accepted=Count(
                "test__finding__id", filter=ACCEPTED_FINDINGS_QUERY
            )
        )
        prefetched_engs = prefetched_engs.prefetch_related("tags")
    else:
        logger.debug("unable to prefetch because query was already executed")

    return prefetched_engs


def view_engagements_cicd(request, pid):
    return view_engagements(request, pid, engagement_type="CI/CD")


def import_scan_results_prod(request, pid=None):
    from dojo.engagement.views import import_scan_results

    return import_scan_results(request, pid=pid)


@user_passes_test(lambda u: u.is_staff)
def new_product(request, ptid=None):
    jira_project_form = None
    error = False
    initial = None
    if ptid is not None:
        prod_type = get_object_or_404(Product_Type, pk=ptid)
        initial = {"prod_type": prod_type}

    form = ProductForm(initial=initial)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=Product())

        if get_system_setting("enable_github"):
            gform = GITHUB_Product_Form(request.POST, instance=GITHUB_PKey())
        else:
            gform = None

        if form.is_valid():
            product = form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Product added successfully.",
                extra_tags="alert-success",
            )
            success, jira_project_form = jira_helper.process_jira_project_form(
                request, product=product
            )
            error = not success

            if get_system_setting("enable_github"):
                if gform.is_valid():
                    github_pkey = gform.save(commit=False)
                    if github_pkey.git_conf is not None and github_pkey.git_project:
                        github_pkey.product = product
                        github_pkey.save()
                        messages.add_message(
                            request,
                            messages.SUCCESS,
                            "GitHub information added successfully.",
                            extra_tags="alert-success",
                        )
                        # Create appropriate labels in the repo
                        logger.info("Create label in repo: " + github_pkey.git_project)
                        try:
                            g = Github(github_pkey.git_conf.api_key)
                            repo = g.get_repo(github_pkey.git_project)
                            repo.create_label(
                                name="security",
                                color="FF0000",
                                description="This label is automatically applied to all issues created by DefectDojo",
                            )
                            repo.create_label(
                                name="security / info",
                                color="00FEFC",
                                description="This label is automatically applied to all issues created by DefectDojo",
                            )
                            repo.create_label(
                                name="security / low",
                                color="B7FE00",
                                description="This label is automatically applied to all issues created by DefectDojo",
                            )
                            repo.create_label(
                                name="security / medium",
                                color="FEFE00",
                                description="This label is automatically applied to all issues created by DefectDojo",
                            )
                            repo.create_label(
                                name="security / high",
                                color="FE9A00",
                                description="This label is automatically applied to all issues created by DefectDojo",
                            )
                            repo.create_label(
                                name="security / critical",
                                color="FE2200",
                                description="This label is automatically applied to all issues created by DefectDojo",
                            )
                        except:
                            logger.info(
                                "Labels cannot be created - they may already exists"
                            )

            # SonarQube API Configuration
            sonarqube_form = Sonarqube_ProductForm(request.POST)
            if sonarqube_form.is_valid():
                sonarqube_product = sonarqube_form.save(commit=False)
                sonarqube_product.product = product
                sonarqube_product.save()

            create_notification(
                event="product_added",
                title=product.name,
                url=reverse("view_product", args=(product.id,)),
            )

            if not error:
                return HttpResponseRedirect(reverse("view_product", args=(product.id,)))
            else:
                # engagement was saved, but JIRA errors, so goto edit_product
                return HttpResponseRedirect(reverse("edit_product", args=(product.id,)))

    jira_project_form = None
    if get_system_setting("enable_jira"):
        jira_project_form = JIRAProjectForm()

    if get_system_setting("enable_github"):
        gform = GITHUB_Product_Form()
    else:
        gform = None

    add_breadcrumb(title="New Product", top_level=False, request=request)
    return render(
        request,
        "dojo/new_product.html",
        {
            "form": form,
            "jform": jira_project_form,
            "gform": gform,
            "sonarqube_form": Sonarqube_ProductForm(),
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def edit_product(request, pid):
    product = Product.objects.get(pk=pid)
    system_settings = System_Settings.objects.get()
    jira_enabled = system_settings.enable_jira
    jira_project = None
    jform = None
    github_enabled = system_settings.enable_github
    github_inst = None
    gform = None
    sonarqube_form = None
    error = False

    try:
        github_inst = GITHUB_PKey.objects.get(product=product)
    except:
        github_inst = None
        pass

    sonarqube_conf = Sonarqube_Product.objects.filter(product=product).first()

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        jira_project = jira_helper.get_jira_project(product)
        if form.is_valid():
            form.save()
            tags = request.POST.getlist("tags")
            messages.add_message(
                request,
                messages.SUCCESS,
                "Product updated successfully.",
                extra_tags="alert-success",
            )

            success, jform = jira_helper.process_jira_project_form(
                request, instance=jira_project, product=product
            )
            error = not success

            if get_system_setting("enable_github") and github_inst:
                gform = GITHUB_Product_Form(request.POST, instance=github_inst)
                # need to handle delete
                try:
                    gform.save()
                except:
                    pass
            elif get_system_setting("enable_github"):
                gform = GITHUB_Product_Form(request.POST)
                if gform.is_valid():
                    new_conf = gform.save(commit=False)
                    new_conf.product_id = pid
                    new_conf.save()
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "GITHUB information updated successfully.",
                        extra_tags="alert-success",
                    )

            # SonarQube API Configuration
            sonarqube_form = Sonarqube_ProductForm(
                request.POST, instance=sonarqube_conf
            )
            if sonarqube_form.is_valid():
                new_conf = sonarqube_form.save(commit=False)
                new_conf.product_id = pid
                new_conf.save()

            if not error:
                return HttpResponseRedirect(reverse("view_product", args=(pid,)))

    form = ProductForm(
        instance=product, initial={"auth_users": product.authorized_users.all()}
    )

    if jira_enabled:
        jira_project = jira_helper.get_jira_project(product)
        jform = JIRAProjectForm(instance=jira_project)
    else:
        jform = None

    if github_enabled and (github_inst is not None):
        if github_inst is not None:
            gform = GITHUB_Product_Form(instance=github_inst)
            gform = GITHUB_Product_Form()
        gform = GITHUB_Product_Form()
    else:
        gform = None

    sonarqube_form = Sonarqube_ProductForm(instance=sonarqube_conf)

    product_tab = Product_Tab(pid, title="Edit Product", tab="settings")
    return render(
        request,
        "dojo/edit_product.html",
        {
            "form": form,
            "product_tab": product_tab,
            "jform": jform,
            "gform": gform,
            "sonarqube_form": sonarqube_form,
            "product": product,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def delete_product(request, pid):
    product = get_object_or_404(Product, pk=pid)
    form = DeleteProductForm(instance=product)

    if request.method == "POST":
        if "id" in request.POST and str(product.id) == request.POST["id"]:
            form = DeleteProductForm(request.POST, instance=product)
            if form.is_valid():
                product.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Product and relationships removed.",
                    extra_tags="alert-success",
                )
                create_notification(
                    event="other",
                    title="Deletion of %s" % product.name,
                    description='The product "%s" was deleted by %s'
                    % (product.name, request.user),
                    url=request.build_absolute_uri(reverse("product")),
                    icon="exclamation-triangle",
                )
                return HttpResponseRedirect(reverse("product"))

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([product])
    rels = collector.nested()

    product_tab = Product_Tab(pid, title="Product", tab="settings")
    return render(
        request,
        "dojo/delete_product.html",
        {
            "product": product,
            "form": form,
            "product_tab": product_tab,
            "rels": rels,
        },
    )


@user_must_be_authorized(
    Product, "staff", "pid"
)  # use arg 0 as using pid causes issues, I think due to cicd being there
def new_eng_for_app(request, pid, cicd=False):
    jira_project_form = None
    jira_project = None
    jira_epic_form = None

    product = Product.objects.get(id=pid)
    jira_error = False
    if not user_is_authorized(request.user, "staff", product):
        raise PermissionDenied

    if request.method == "POST":
        form = EngForm(request.POST, cicd=cicd, product=product, user=request.user)
        jira_project = jira_helper.get_jira_project(product)
        logger.debug("new_eng_for_app")

        if form.is_valid():
            # first create the new engagement
            engagement = form.save(commit=False)
            if not engagement.name:
                engagement.name = str(engagement.target_start)
            engagement.threat_model = False
            engagement.api_test = False
            engagement.pen_test = False
            engagement.check_list = False
            engagement.product = form.cleaned_data.get("product")
            if engagement.threat_model:
                engagement.progress = "threat_model"
            else:
                engagement.progress = "other"
            if cicd:
                engagement.engagement_type = "CI/CD"
                engagement.status = "In Progress"
            engagement.active = True

            engagement.save()
            form.save_m2m()

            logger.debug("new_eng_for_app: process jira coming")

            # new engagement, so do not provide jira_project
            success, jira_project_form = jira_helper.process_jira_project_form(
                request, instance=None, engagement=engagement
            )
            error = not success

            logger.debug("new_eng_for_app: process jira epic coming")

            success, jira_epic_form = jira_helper.process_jira_epic_form(
                request, engagement=engagement
            )
            error = error or not success

            create_notification(
                event="engagement_added",
                title=engagement.name + " for " + product.name,
                engagement=engagement,
                url=reverse("view_engagement", args=(engagement.id,)),
                objowner=engagement.lead,
            )

            messages.add_message(
                request,
                messages.SUCCESS,
                "Engagement added successfully.",
                extra_tags="alert-success",
            )

            if not error:
                if "_Add Tests" in request.POST:
                    return HttpResponseRedirect(
                        reverse("add_tests", args=(engagement.id,))
                    )
                elif "_Import Scan Results" in request.POST:
                    return HttpResponseRedirect(
                        reverse("import_scan_results", args=(engagement.id,))
                    )
                else:
                    return HttpResponseRedirect(
                        reverse("view_engagement", args=(engagement.id,))
                    )
            else:
                # engagement was saved, but JIRA errors, so goto edit_engagement
                logger.debug("new_eng_for_app: jira errors")
                return HttpResponseRedirect(
                    reverse("edit_engagement", args=(engagement.id,))
                )
        else:
            logger.debug(form.errors)

    form = EngForm(
        initial={
            "lead": request.user,
            "target_start": timezone.now().date(),
            "target_end": timezone.now().date() + timedelta(days=7),
            "product": product,
        },
        cicd=cicd,
        product=product,
        user=request.user,
    )
    jira_project_form = None
    jira_epic_form = None
    if get_system_setting("enable_jira"):
        jira_project = jira_helper.get_jira_project(product)
        logger.debug("showing jira-project-form")
        jira_project_form = JIRAProjectForm(target="engagement", product=product)
        logger.debug("showing jira-epic-form")
        jira_epic_form = JIRAEngagementForm()

    product_tab = Product_Tab(pid, title="New Engagement", tab="engagements")
    return render(
        request,
        "dojo/new_eng.html",
        {
            "form": form,
            "product_tab": product_tab,
            "jira_epic_form": jira_epic_form,
            "jira_project_form": jira_project_form,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def new_tech_for_prod(request, pid):
    prod = Product.objects.get(id=pid)
    if request.method == "POST":
        form = App_AnalysisTypeForm(request.POST)
        if form.is_valid():
            tech = form.save(commit=False)
            tech.product_id = pid
            tech.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Technology added successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("view_product", args=(pid,)))

    form = App_AnalysisTypeForm()
    return render(request, "dojo/new_tech.html", {"form": form, "pid": pid})


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def new_eng_for_app_cicd(request, pid):
    # we have to use pid=pid here as new_eng_for_app expects kwargs, because that is how django calls the function based on urls.py named groups
    return new_eng_for_app(request, pid=pid, cicd=True)


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def add_meta_data(request, pid):
    prod = Product.objects.get(id=pid)
    if request.method == "POST":
        form = DojoMetaDataForm(request.POST, instance=DojoMeta(product=prod))
        if form.is_valid():
            form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Metadata added successfully.",
                extra_tags="alert-success",
            )
            if "add_another" in request.POST:
                return HttpResponseRedirect(reverse("add_meta_data", args=(pid,)))
            else:
                return HttpResponseRedirect(reverse("view_product", args=(pid,)))
    else:
        form = DojoMetaDataForm()

    product_tab = Product_Tab(pid, title="Add Metadata", tab="settings")

    return render(
        request,
        "dojo/add_product_meta_data.html",
        {
            "form": form,
            "product_tab": product_tab,
            "product": prod,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def edit_meta_data(request, pid):
    prod = Product.objects.get(id=pid)
    if request.method == "POST":
        for key, value in request.POST.items():
            if key.startswith("cfv_"):
                cfv_id = int(key.split("_")[1])
                cfv = get_object_or_404(DojoMeta, id=cfv_id)
                value = value.strip()
                if value:
                    cfv.value = value
                    cfv.save()
            if key.startswith("delete_"):
                cfv_id = int(key.split("_")[2])
                cfv = get_object_or_404(DojoMeta, id=cfv_id)
                cfv.delete()

        messages.add_message(
            request,
            messages.SUCCESS,
            "Metadata edited successfully.",
            extra_tags="alert-success",
        )
        return HttpResponseRedirect(reverse("view_product", args=(pid,)))

    product_tab = Product_Tab(pid, title="Edit Metadata", tab="settings")
    return render(
        request,
        "dojo/edit_product_meta_data.html",
        {
            "product": prod,
            "product_tab": product_tab,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def ad_hoc_finding(request, pid):
    prod = Product.objects.get(id=pid)
    test = None
    try:
        eng = Engagement.objects.get(product=prod, name="Ad Hoc Engagement")
        tests = Test.objects.filter(engagement=eng)

        if len(tests) != 0:
            test = tests[0]
        else:
            test = Test(
                engagement=eng,
                test_type=Test_Type.objects.get(name="Pen Test"),
                target_start=timezone.now(),
                target_end=timezone.now(),
            )
            test.save()
    except:
        eng = Engagement(
            name="Ad Hoc Engagement",
            target_start=timezone.now(),
            target_end=timezone.now(),
            active=False,
            product=prod,
        )
        eng.save()
        test = Test(
            engagement=eng,
            test_type=Test_Type.objects.get(name="Pen Test"),
            target_start=timezone.now(),
            target_end=timezone.now(),
        )
        test.save()
    form_error = False
    push_all_jira_issues = jira_helper.is_push_all_issues(test)
    jform = None
    gform = None
    form = AdHocFindingForm(initial={"date": timezone.now().date()}, req_resp=None)
    use_jira = jira_helper.get_jira_project(test) is not None

    if request.method == "POST":
        form = AdHocFindingForm(request.POST, req_resp=None)
        if (form["active"].value() is False or form["false_p"].value()) and form[
            "duplicate"
        ].value() is False:
            closing_disabled = Note_Type.objects.filter(
                is_mandatory=True, is_active=True
            ).count()
            if closing_disabled != 0:
                error_inactive = ValidationError(
                    "Can not set a finding as inactive without adding all mandatory notes",
                    code="inactive_without_mandatory_notes",
                )
                error_false_p = ValidationError(
                    "Can not set a finding as false positive without adding all mandatory notes",
                    code="false_p_without_mandatory_notes",
                )
                if form["active"].value() is False:
                    form.add_error("active", error_inactive)
                if form["false_p"].value():
                    form.add_error("false_p", error_false_p)
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Can not set a finding as inactive or false positive without adding all mandatory notes",
                    extra_tags="alert-danger",
                )
        if use_jira:
            jform = JIRAFindingForm(
                request.POST,
                prefix="jiraform",
                push_all=push_all_jira_issues,
                jira_project=jira_helper.get_jira_project(test),
            )

        if form.is_valid() and (jform is None or jform.is_valid()):
            new_finding = form.save(commit=False)
            new_finding.test = test
            new_finding.reporter = request.user
            new_finding.numerical_severity = Finding.get_numerical_severity(
                new_finding.severity
            )
            finding_helper.update_finding_status(new_finding, request.user)
            create_template = new_finding.is_template
            # always false now since this will be deprecated soon in favor of new Finding_Template model
            new_finding.is_template = False
            new_finding.save()
            new_finding.endpoints.set(form.cleaned_data["endpoints"])
            for endpoint in form.cleaned_data["endpoints"]:
                eps, created = Endpoint_Status.objects.get_or_create(
                    finding=new_finding, endpoint=endpoint
                )
                endpoint.endpoint_status.add(eps)
                new_finding.endpoint_status.add(eps)

            for endpoint in new_finding.unsaved_endpoints:
                ep, created = Endpoint.objects.get_or_create(
                    protocol=endpoint.protocol,
                    host=endpoint.host,
                    path=endpoint.path,
                    query=endpoint.query,
                    fragment=endpoint.fragment,
                    product=test.engagement.product,
                )
                eps, created = Endpoint_Status.objects.get_or_create(
                    finding=new_finding, endpoint=ep
                )
                ep.endpoint_status.add(eps)

                new_finding.endpoints.add(ep)
                new_finding.endpoint_status.add(eps)
            for endpoint in form.cleaned_data["endpoints"]:
                ep, created = Endpoint.objects.get_or_create(
                    protocol=endpoint.protocol,
                    host=endpoint.host,
                    path=endpoint.path,
                    query=endpoint.query,
                    fragment=endpoint.fragment,
                    product=test.engagement.product,
                )
                eps, created = Endpoint_Status.objects.get_or_create(
                    finding=new_finding, endpoint=ep
                )
                ep.endpoint_status.add(eps)

                new_finding.endpoints.add(ep)
                new_finding.endpoint_status.add(eps)

            new_finding.save()
            # Push to jira?
            push_to_jira = False
            jira_message = None
            if jform and jform.is_valid():
                # Push to Jira?
                logger.debug("jira form valid")
                push_to_jira = push_all_jira_issues or jform.cleaned_data.get(
                    "push_to_jira"
                )

                # if the jira issue key was changed, update database
                new_jira_issue_key = jform.cleaned_data.get("jira_issue")
                if new_finding.has_jira_issue:
                    jira_issue = new_finding.jira_issue

                    # everything in DD around JIRA integration is based on the internal id of the issue in JIRA
                    # instead of on the public jira issue key.
                    # I have no idea why, but it means we have to retrieve the issue from JIRA to get the internal JIRA id.
                    # we can assume the issue exist, which is already checked in the validation of the jform

                    if not new_jira_issue_key:
                        jira_helper.finding_unlink_jira(request, new_finding)
                        jira_message = "Link to JIRA issue removed successfully."

                    elif new_jira_issue_key != new_finding.jira_issue.jira_key:
                        jira_helper.finding_unlink_jira(request, new_finding)
                        jira_helper.finding_link_jira(
                            request, new_finding, new_jira_issue_key
                        )
                        jira_message = "Changed JIRA link successfully."
                else:
                    logger.debug("finding has no jira issue yet")
                    if new_jira_issue_key:
                        logger.debug(
                            "finding has no jira issue yet, but jira issue specified in request. trying to link."
                        )
                        jira_helper.finding_link_jira(
                            request, new_finding, new_jira_issue_key
                        )
                        jira_message = "Linked a JIRA issue successfully."

            if "githubform-push_to_github" in request.POST:
                gform = GITHUBFindingForm(
                    request.POST, prefix="jiragithub", enabled=push_all_jira_issues
                )
                if gform.is_valid():
                    add_external_issue(new_finding, "github")

            new_finding.save(push_to_jira=push_to_jira)

            if "request" in form.cleaned_data or "response" in form.cleaned_data:
                burp_rr = BurpRawRequestResponse(
                    finding=new_finding,
                    burpRequestBase64=base64.b64encode(
                        form.cleaned_data["request"].encode()
                    ),
                    burpResponseBase64=base64.b64encode(
                        form.cleaned_data["response"].encode()
                    ),
                )
                burp_rr.clean()
                burp_rr.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Finding added successfully.",
                extra_tags="alert-success",
            )

            if create_template:
                templates = Finding_Template.objects.filter(title=new_finding.title)
                if len(templates) > 0:
                    messages.add_message(
                        request,
                        messages.ERROR,
                        "A finding template was not created.  A template with this title already "
                        "exists.",
                        extra_tags="alert-danger",
                    )
                else:
                    template = Finding_Template(
                        title=new_finding.title,
                        cwe=new_finding.cwe,
                        severity=new_finding.severity,
                        description=new_finding.description,
                        mitigation=new_finding.mitigation,
                        impact=new_finding.impact,
                        references=new_finding.references,
                        numerical_severity=new_finding.numerical_severity,
                    )
                    template.save()
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "A finding template was also created.",
                        extra_tags="alert-success",
                    )
            if "_Finished" in request.POST:
                return HttpResponseRedirect(reverse("view_test", args=(test.id,)))
            else:
                return HttpResponseRedirect(reverse("add_findings", args=(test.id,)))
        else:
            if "endpoints" in form.cleaned_data:
                form.fields["endpoints"].queryset = form.cleaned_data["endpoints"]
            else:
                form.fields["endpoints"].queryset = Endpoint.objects.none()
            form_error = True
            messages.add_message(
                request,
                messages.ERROR,
                "The form has errors, please correct them below.",
                extra_tags="alert-danger",
            )
    else:
        if use_jira:
            jform = JIRAFindingForm(
                push_all=jira_helper.is_push_all_issues(test),
                prefix="jiraform",
                jira_project=jira_helper.get_jira_project(test),
            )

        if get_system_setting("enable_github"):
            if GITHUB_PKey.objects.filter(product=test.engagement.product).count() != 0:
                gform = GITHUBFindingForm(
                    enabled=push_all_jira_issues, prefix="githubform"
                )
        else:
            gform = None

    product_tab = Product_Tab(pid, title="Add Finding", tab="engagements")
    product_tab.setEngagement(eng)
    return render(
        request,
        "dojo/ad_hoc_findings.html",
        {
            "form": form,
            "product_tab": product_tab,
            "temp": False,
            "tid": test.id,
            "pid": pid,
            "form_error": form_error,
            "jform": jform,
            "gform": gform,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def engagement_presets(request, pid):
    prod = get_object_or_404(Product, id=pid)
    presets = Engagement_Presets.objects.filter(product=prod).all()

    product_tab = Product_Tab(prod.id, title="Engagement Presets", tab="settings")

    return render(
        request,
        "dojo/view_presets.html",
        {"product_tab": product_tab, "presets": presets, "prod": prod},
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def edit_engagement_presets(request, pid, eid):
    prod = get_object_or_404(Product, id=pid)
    preset = get_object_or_404(Engagement_Presets, id=eid)

    product_tab = Product_Tab(prod.id, title="Edit Engagement Preset", tab="settings")

    if request.method == "POST":
        tform = EngagementPresetsForm(request.POST, instance=preset)
        if tform.is_valid():
            tform.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Engagement Preset Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("engagement_presets", args=(pid,)))
    else:
        tform = EngagementPresetsForm(instance=preset)

    return render(
        request,
        "dojo/edit_presets.html",
        {"product_tab": product_tab, "tform": tform, "prod": prod},
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def add_engagement_presets(request, pid):
    prod = get_object_or_404(Product, id=pid)
    if request.method == "POST":
        tform = EngagementPresetsForm(request.POST)
        if tform.is_valid():
            form_copy = tform.save(commit=False)
            form_copy.product = prod
            form_copy.save()
            tform.save_m2m()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Engagement Preset Successfully Created.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("engagement_presets", args=(pid,)))
    else:
        tform = EngagementPresetsForm()

    product_tab = Product_Tab(pid, title="New Engagement Preset", tab="settings")
    return render(
        request,
        "dojo/new_params.html",
        {"tform": tform, "pid": pid, "product_tab": product_tab},
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def delete_engagement_presets(request, pid, eid):
    prod = get_object_or_404(Product, id=pid)
    preset = get_object_or_404(Engagement_Presets, id=eid)
    form = DeleteEngagementPresetsForm(instance=preset)

    if request.method == "POST":
        if "id" in request.POST:
            form = DeleteEngagementPresetsForm(request.POST, instance=preset)
            if form.is_valid():
                preset.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Engagement presets and engagement relationships removed.",
                    extra_tags="alert-success",
                )
                return HttpResponseRedirect(reverse("engagement_presets", args=(pid,)))

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([preset])
    rels = collector.nested()

    product_tab = Product_Tab(pid, title="Delete Engagement Preset", tab="settings")
    return render(
        request,
        "dojo/delete_presets.html",
        {
            "product": product,
            "form": form,
            "product_tab": product_tab,
            "rels": rels,
        },
    )


def edit_notifications(request, pid):
    prod = get_object_or_404(Product, id=pid)
    if request.method == "POST":
        product_notifications = (
            Notifications.objects.filter(user=request.user).filter(product=prod).first()
        )
        if not product_notifications:
            product_notifications = Notifications(user=request.user, product=prod)
            logger.debug("no existing product notifications found")
        else:
            logger.debug("existing product notifications found")

        form = ProductNotificationsForm(request.POST, instance=product_notifications)
        # print(vars(form))

        if form.is_valid():
            form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Notification settings updated.",
                extra_tags="alert-success",
            )

    return HttpResponseRedirect(reverse("view_product", args=(pid,)))
