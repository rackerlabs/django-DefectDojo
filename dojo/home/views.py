# #  dojo home pages
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone

from dojo.models import Finding, Engagement, Risk_Acceptance
from django.db.models import Count
from dojo.utils import add_breadcrumb, get_punchcard_data
from dojo.finding.views import ACCEPTED_FINDINGS_QUERY
from dojo.models import Answered_Survey


logger = logging.getLogger(__name__)


def home(request):
    if request.user.is_authenticated and request.user.is_staff:
        return HttpResponseRedirect(reverse("dashboard"))
    return HttpResponseRedirect(reverse("product"))


@user_passes_test(lambda u: u.is_staff)
def dashboard(request):
    now = timezone.now()
    seven_days_ago = now - timedelta(days=6)  # 6 days plus today

    if request.user.is_superuser:
        engagement_count = Engagement.objects.filter(active=True).count()
        finding_count = Finding.objects.filter(
            verified=True,
            mitigated=None,
            duplicate=False,
            date__range=[seven_days_ago, now],
        ).count()
        mitigated_count = Finding.objects.filter(
            mitigated__date__range=[seven_days_ago, now]
        ).count()

        accepted_findings = Finding.objects.filter(
            risk_acceptance__created__date__range=[seven_days_ago, now]
        )
        accepted_findings = accepted_findings.filter(ACCEPTED_FINDINGS_QUERY)
        accepted_count = accepted_findings.count()

        # forever counts
        findings = Finding.objects.filter(verified=True, duplicate=False)
    else:
        engagement_count = Engagement.objects.filter(
            lead=request.user, active=True
        ).count()
        finding_count = Finding.objects.filter(
            reporter=request.user,
            verified=True,
            duplicate=False,
            mitigated=None,
            date__range=[seven_days_ago, now],
        ).count()
        mitigated_count = Finding.objects.filter(
            mitigated_by=request.user, mitigated__date__range=[seven_days_ago, now]
        ).count()

        accepted_count = len(
            [
                finding
                for ra in Risk_Acceptance.objects.filter(
                    owner=request.user, created__date__range=[seven_days_ago, now]
                )
                for finding in ra.accepted_findings.all()
            ]
        )

        # forever counts
        findings = Finding.objects.filter(
            reporter=request.user, verified=True, duplicate=False
        )

    severity_count_all = get_severities_all(findings)
    severity_count_by_month = get_severities_by_month(findings)

    start_date = timezone.now() - relativedelta(weeks=26)
    punchcard, ticks = get_punchcard_data(findings, start_date, 26)

    unassigned_surveys = Answered_Survey.objects.all().filter(
        assignee_id__isnull=True, completed__gt=0
    )

    add_breadcrumb(request=request, clear=True)
    return render(
        request,
        "dojo/dashboard.html",
        {
            "engagement_count": engagement_count,
            "finding_count": finding_count,
            "mitigated_count": mitigated_count,
            "accepted_count": accepted_count,
            "critical": severity_count_all["Critical"],
            "high": severity_count_all["High"],
            "medium": severity_count_all["Medium"],
            "low": severity_count_all["Low"],
            "info": severity_count_all["Info"],
            "by_month": severity_count_by_month,
            "punchcard": punchcard,
            "ticks": ticks,
            "surveys": unassigned_surveys,
        },
    )


def get_severities_all(findings):
    # order_by is needed due to ordering being present in Meta of Finding
    severities_all = (
        findings.values("severity").annotate(count=Count("severity")).order_by()
    )

    # make sure all keys are present
    sev_counts_all = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}

    for s in severities_all:
        sev_counts_all[s["severity"]] = s["count"]

    return sev_counts_all


def get_severities_by_month(findings):
    by_month = list()

    # order_by is needed due to ordering being present in Meta of Finding
    # severities_all = findings.values('severity').annotate(count=Count('severity')).order_by()
    start_date = timezone.make_aware(
        datetime.combine(timezone.localdate(), datetime.min.time())
    )
    severities_by_month = (
        findings.filter(created__gte=start_date + relativedelta(months=-6))
        .values("created__year", "created__month", "severity")
        .annotate(count=Count("severity"))
        .order_by("created__year", "created__month")
    )

    results = {}
    for ms in severities_by_month:
        year = str(ms["created__year"])
        month = str(ms["created__month"]).zfill(2)
        key = year + "-" + month

        if key not in results:
            # graph expects a, b, c, d, e instead of Critical, High, ...
            sourcedata = {"y": key, "a": 0, "b": 0, "c": 0, "d": 0, "e": 0}
            results[key] = sourcedata

        month_stats = results[key]

        if ms["severity"] == "Critical":
            month_stats["a"] = ms["count"]
        elif ms["severity"] == "High":
            month_stats["b"] = ms["count"]
        elif ms["severity"] == "Medium":
            month_stats["c"] = ms["count"]
        elif ms["severity"] == "Low":
            month_stats["d"] = ms["count"]
        elif ms["severity"] == "Info":
            month_stats["e"] = ms["count"]

    by_month = [v for k, v in sorted(results.items())]
    return by_month
