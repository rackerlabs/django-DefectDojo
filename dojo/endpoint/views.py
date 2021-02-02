import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils.html import escape
from django.utils import timezone
from django.contrib.admin.utils import NestedObjects
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Q, QuerySet, Count
from dojo.filters import EndpointFilter
from dojo.forms import (
    EditEndpointForm,
    DeleteEndpointForm,
    AddEndpointForm,
    DojoMetaDataForm,
)
from dojo.models import (
    Product,
    Endpoint,
    Finding,
    System_Settings,
    DojoMeta,
    Endpoint_Status,
)
from dojo.utils import (
    get_page_items,
    add_breadcrumb,
    get_period_counts,
    get_system_setting,
    Product_Tab,
    calculate_grade,
    redirect,
)
from dojo.notifications.helper import create_notification
from dojo.user.helper import user_must_be_authorized

logger = logging.getLogger(__name__)


def vulnerable_endpoints(request):
    endpoints = Endpoint.objects.filter(
        finding__active=True,
        finding__verified=True,
        finding__false_p=False,
        finding__duplicate=False,
        finding__out_of_scope=False,
        mitigated=False,
    ).distinct()

    # are they authorized
    if request.user.is_staff:
        pass
    else:
        endpoints = Endpoint.objects.filter(
            Q(product__authorized_users__in=[request.user])
            | Q(product__prod_type__authorized_users__in=[request.user])
        )
        if not endpoints:
            raise PermissionDenied

    product = None
    if "product" in request.GET:
        p = request.GET.getlist("product", [])
        if len(p) == 1:
            product = get_object_or_404(Product, id=p[0])

    ids = get_endpoint_ids(
        EndpointFilter(request.GET, queryset=endpoints, user=request.user).qs
    )
    endpoints = EndpointFilter(
        request.GET, queryset=endpoints.filter(id__in=ids), user=request.user
    )
    endpoints_query = endpoints.qs.order_by("host")
    paged_endpoints = get_page_items(request, endpoints_query, 25)
    add_breadcrumb(
        title="Vulnerable Endpoints", top_level=not len(request.GET), request=request
    )

    system_settings = System_Settings.objects.get()

    product_tab = None
    view_name = "All Endpoints"
    if product:
        product_tab = Product_Tab(product.id, "Vulnerable Endpoints", tab="endpoints")
    return render(
        request,
        "dojo/endpoints.html",
        {
            "product_tab": product_tab,
            "endpoints": paged_endpoints,
            "filtered": endpoints,
            "name": "Vulnerable Endpoints",
        },
    )


def all_endpoints(request):
    endpoints = Endpoint.objects.all()
    show_uri = get_system_setting("display_endpoint_uri")
    # are they authorized
    if request.user.is_staff:
        pass
    else:
        endpoints = Endpoint.objects.filter(
            Q(product__authorized_users__in=[request.user])
            | Q(product__prod_type__authorized_users__in=[request.user])
        )
        if not endpoints:
            raise PermissionDenied

    product = None
    if "product" in request.GET:
        p = request.GET.getlist("product", [])
        if len(p) == 1:
            product = get_object_or_404(Product, id=p[0])

    if show_uri:
        endpoints = EndpointFilter(request.GET, queryset=endpoints, user=request.user)
        paged_endpoints = get_page_items(request, endpoints.qs, 25)
    else:
        ids = get_endpoint_ids(
            EndpointFilter(request.GET, queryset=endpoints, user=request.user).qs
        )
        endpoints = EndpointFilter(
            request.GET, queryset=endpoints.filter(id__in=ids), user=request.user
        )
        paged_endpoints = get_page_items(request, endpoints.qs, 25)
    add_breadcrumb(
        title="All Endpoints", top_level=not len(request.GET), request=request
    )

    product_tab = None
    view_name = "All Endpoints"
    if product:
        view_name = "Endpoints"
        product_tab = Product_Tab(product.id, "Endpoints", tab="endpoints")

    return render(
        request,
        "dojo/endpoints.html",
        {
            "product_tab": product_tab,
            "endpoints": paged_endpoints,
            "filtered": endpoints,
            "name": view_name,
            "show_uri": show_uri,
        },
    )


def get_endpoint_ids(endpoints):
    hosts = []
    ids = []
    for e in endpoints:
        if ":" in e.host:
            host_no_port = e.host[: e.host.index(":")]
        else:
            host_no_port = e.host
        key = host_no_port + "-" + str(e.product.id)
        if key in hosts:
            continue
        else:
            hosts.append(key)
            ids.append(e.id)
    return ids


@user_must_be_authorized(Endpoint, "view", "eid")
def view_endpoint(request, eid):
    endpoint = get_object_or_404(Endpoint, id=eid)
    host = endpoint.host_no_port
    endpoints = Endpoint.objects.filter(
        host__regex="^" + host + ":?", product=endpoint.product
    ).distinct()

    endpoint_metadata = dict(endpoint.endpoint_meta.values_list("name", "value"))

    all_findings = Finding.objects.filter(endpoints__in=endpoints).distinct()

    active_findings = Finding.objects.filter(
        endpoints__in=endpoints, active=True, verified=True
    ).distinct()

    closed_findings = Finding.objects.filter(
        endpoints__in=endpoints, mitigated__isnull=False
    ).distinct()
    if all_findings:
        start_date = timezone.make_aware(
            datetime.combine(all_findings.last().date, datetime.min.time())
        )
    else:
        start_date = timezone.now()
    end_date = timezone.now()

    r = relativedelta(end_date, start_date)
    months_between = (r.years * 12) + r.months
    # include current month
    months_between += 1

    monthly_counts = get_period_counts(
        active_findings,
        all_findings,
        closed_findings,
        None,
        months_between,
        start_date,
        relative_delta="months",
    )

    paged_findings = get_page_items(request, active_findings, 25)

    vulnerable = False

    if active_findings.count() != 0:
        vulnerable = True

    product_tab = Product_Tab(endpoint.product.id, "Endpoint", tab="endpoints")
    return render(
        request,
        "dojo/view_endpoint.html",
        {
            "endpoint": endpoint,
            "product_tab": product_tab,
            "endpoints": endpoints,
            "findings": paged_findings,
            "all_findings": all_findings,
            "opened_per_month": monthly_counts["opened_per_period"],
            "endpoint_metadata": endpoint_metadata,
            "vulnerable": vulnerable,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Endpoint, "change", "eid")
def edit_endpoint(request, eid):
    endpoint = get_object_or_404(Endpoint, id=eid)

    if request.method == "POST":
        form = EditEndpointForm(request.POST, instance=endpoint)
        if form.is_valid():
            logger.debug("saving endpoint")
            endpoint = form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Endpoint updated successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("view_endpoint", args=(endpoint.id,)))
    else:
        add_breadcrumb(parent=endpoint, title="Edit", top_level=False, request=request)
        form = EditEndpointForm(instance=endpoint)

    product_tab = Product_Tab(endpoint.product.id, "Endpoint", tab="endpoints")

    return render(
        request,
        "dojo/edit_endpoint.html",
        {
            "endpoint": endpoint,
            "product_tab": product_tab,
            "form": form,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Endpoint, "delete", "eid")
def delete_endpoint(request, eid):
    endpoint = get_object_or_404(Endpoint, pk=eid)
    product = endpoint.product
    form = DeleteEndpointForm(instance=endpoint)

    if request.method == "POST":
        if "id" in request.POST and str(endpoint.id) == request.POST["id"]:
            form = DeleteEndpointForm(request.POST, instance=endpoint)
            if form.is_valid():
                endpoint.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Endpoint and relationships removed.",
                    extra_tags="alert-success",
                )
                create_notification(
                    event="other",
                    title="Deletion of %s" % endpoint,
                    description='The endpoint "%s" was deleted by %s'
                    % (endpoint, request.user),
                    url=request.build_absolute_uri(reverse("endpoints")),
                    icon="exclamation-triangle",
                )
                return HttpResponseRedirect(reverse("view_product", args=(product.id,)))

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([endpoint])
    rels = collector.nested()

    product_tab = Product_Tab(endpoint.product.id, "Delete Endpoint", tab="endpoints")

    return render(
        request,
        "dojo/delete_endpoint.html",
        {
            "endpoint": endpoint,
            "product_tab": product_tab,
            "form": form,
            "rels": rels,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Product, "staff", "pid")
def add_endpoint(request, pid):
    product = get_object_or_404(Product, id=pid)
    template = "dojo/add_endpoint.html"

    form = AddEndpointForm(product=product)
    if request.method == "POST":
        form = AddEndpointForm(request.POST, product=product)
        if form.is_valid():
            endpoints = form.save()
            tags = request.POST.get("tags")
            for e in endpoints:
                e.tags = tags
                e.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Endpoint added successfully.",
                extra_tags="alert-success",
            )
            if "_popup" in request.GET:
                resp = '<script type="text/javascript">opener.emptyEndpoints(window);</script>'
                for endpoint in endpoints:
                    resp += (
                        '<script type="text/javascript">opener.dismissAddAnotherPopupDojo(window, "%s", "%s");</script>'
                        % (escape(endpoint._get_pk_val()), escape(endpoint))
                    )
                resp += '<script type="text/javascript">window.close();</script>'
                return HttpResponse(resp)
            else:
                return HttpResponseRedirect(reverse("endpoints") + "?product=" + pid)

    product_tab = None
    if "_popup" not in request.GET:
        product_tab = Product_Tab(product.id, "Add Endpoint", tab="endpoints")

    return render(
        request,
        template,
        {"product_tab": product_tab, "name": "Add Endpoint", "form": form},
    )


@user_passes_test(lambda u: u.is_staff)
def add_product_endpoint(request):
    form = AddEndpointForm()
    if request.method == "POST":
        form = AddEndpointForm(request.POST)
        if form.is_valid():
            endpoints = form.save()
            tags = request.POST.get("tags")
            for e in endpoints:
                e.tags = tags
                e.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Endpoint added successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse("endpoints") + "?product=%s" % form.product.id
            )
    add_breadcrumb(title="Add Endpoint", top_level=False, request=request)
    return render(
        request,
        "dojo/add_endpoint.html",
        {
            "name": "Add Endpoint",
            "form": form,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Endpoint, "staff", "eid")
def add_meta_data(request, eid):
    endpoint = Endpoint.objects.get(id=eid)
    if request.method == "POST":
        form = DojoMetaDataForm(request.POST, instance=DojoMeta(endpoint=endpoint))
        if form.is_valid():
            form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Metadata added successfully.",
                extra_tags="alert-success",
            )
            if "add_another" in request.POST:
                return HttpResponseRedirect(reverse("add_meta_data", args=(eid,)))
            else:
                return HttpResponseRedirect(reverse("view_endpoint", args=(eid,)))
    else:
        form = DojoMetaDataForm()

    add_breadcrumb(
        parent=endpoint, title="Add Metadata", top_level=False, request=request
    )
    product_tab = Product_Tab(endpoint.product.id, "Add Metadata", tab="endpoints")
    return render(
        request,
        "dojo/add_endpoint_meta_data.html",
        {
            "form": form,
            "product_tab": product_tab,
            "endpoint": endpoint,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Endpoint, "change", "eid")
def edit_meta_data(request, eid):
    endpoint = Endpoint.objects.get(id=eid)

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
        return HttpResponseRedirect(reverse("view_endpoint", args=(eid,)))

    product_tab = Product_Tab(endpoint.product.id, "Edit Metadata", tab="endpoints")
    return render(
        request,
        "dojo/edit_endpoint_meta_data.html",
        {
            "endpoint": endpoint,
            "product_tab": product_tab,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def endpoint_bulk_update_all(request, pid=None):
    if request.method == "POST":
        endpoints_to_update = request.POST.getlist("endpoints_to_update")
        if request.POST.get("delete_bulk_endpoints") and endpoints_to_update:
            finds = Endpoint.objects.filter(id__in=endpoints_to_update)
            product_calc = list(
                Product.objects.filter(endpoint__id__in=endpoints_to_update).distinct()
            )
            finds.delete()
            for prod in product_calc:
                calculate_grade(prod)
        else:
            if endpoints_to_update:
                endpoints_to_update = request.POST.getlist("endpoints_to_update")
                finds = Endpoint.objects.filter(id__in=endpoints_to_update).order_by(
                    "endpoint_meta__product__id"
                )
                for endpoint in finds:
                    endpoint.mitigated = not endpoint.mitigated
                    endpoint.save()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Bulk edit of endpoints was successful.  Check to make sure it is what you intended.",
                    extra_tags="alert-success",
                )
            else:
                # raise Exception('STOP')
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Unable to process bulk update. Required fields were not selected.",
                    extra_tags="alert-danger",
                )
    return HttpResponseRedirect(reverse("endpoints", args=()))


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Finding, "staff", "fid")
def endpoint_status_bulk_update(request, fid):
    if request.method == "POST":
        post = request.POST
        endpoints_to_update = post.getlist("endpoints_to_update")
        status_list = [
            "active",
            "false_positive",
            "mitigated",
            "out_of_scope",
            "risk_accepted",
        ]
        enable = [item for item in status_list if item in list(post.keys())]

        if endpoints_to_update and len(enable) > 0:
            endpoints = Endpoint.objects.filter(id__in=endpoints_to_update).order_by(
                "endpoint_meta__product__id"
            )
            for endpoint in endpoints:
                endpoint_status = Endpoint_Status.objects.get(
                    endpoint=endpoint, finding__id=fid
                )
                for status in status_list:
                    if status in enable:
                        endpoint_status.__setattr__(status, True)
                        if status == "mitigated":
                            endpoint_status.mitigated_by = request.user
                            endpoint_status.mitigated_time = timezone.now()
                    else:
                        endpoint_status.__setattr__(status, False)
                endpoint_status.last_modified = timezone.now()
                endpoint_status.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Bulk edit of endpoints was successful. Check to make sure it is what you intended.",
                extra_tags="alert-success",
            )
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Unable to process bulk update. Required fields were not selected.",
                extra_tags="alert-danger",
            )
    return redirect(request, post["return_url"])


def prefetch_for_endpoints(endpoints):
    if isinstance(endpoints, QuerySet):
        endpoints = endpoints.prefetch_related("product", "tags", "product__tags")
        endpoints = endpoints.annotate(
            active_finding_count=Count("finding__id", filter=Q(finding__active=True))
        )
    else:
        logger.debug("unable to prefetch because query was already executed")

    return endpoints
