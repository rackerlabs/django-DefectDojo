import logging
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from dojo.models import Product, Objects_Product, Objects_Engagement, Engagement
from dojo.forms import ObjectSettingsForm, DeleteObjectsSettingsForm
from dojo.utils import Product_Tab

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_staff)
def new_object(request, pid):
    prod = get_object_or_404(Product, id=pid)
    if request.method == "POST":
        tform = ObjectSettingsForm(request.POST)
        if tform.is_valid():
            new_prod = tform.save(commit=False)
            new_prod.product = prod
            new_prod.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Added Tracked File to a Product",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("view_objects", args=(pid,)))
    else:
        tform = ObjectSettingsForm()
        product_tab = Product_Tab(
            pid, title="Add Tracked Files to a Product", tab="settings"
        )

        return render(
            request,
            "dojo/new_object.html",
            {"tform": tform, "product_tab": product_tab, "pid": prod.id},
        )


@user_passes_test(lambda u: u.is_staff)
def view_objects(request, pid):
    object_queryset = Objects_Product.objects.filter(product=pid).order_by(
        "path", "folder", "artifact"
    )

    product_tab = Product_Tab(
        pid, title="Tracked Product Files, Paths and Artifacts", tab="settings"
    )
    return render(
        request,
        "dojo/view_objects.html",
        {"object_queryset": object_queryset, "product_tab": product_tab, "pid": pid},
    )


@user_passes_test(lambda u: u.is_staff)
def edit_object(request, pid, ttid):
    object = Objects_Product.objects.get(pk=ttid)

    if request.method == "POST":
        tform = ObjectSettingsForm(request.POST, instance=object)
        if tform.is_valid():
            tform.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Tool Product Configuration Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("view_objects", args=(pid,)))
    else:
        tform = ObjectSettingsForm(instance=object)

    product_tab = Product_Tab(pid, title="Edit Tracked Files", tab="settings")
    return render(
        request, "dojo/edit_object.html", {"tform": tform, "product_tab": product_tab}
    )


@user_passes_test(lambda u: u.is_staff)
def delete_object(request, pid, ttid):
    object = Objects_Product.objects.get(pk=ttid)

    if request.method == "POST":
        tform = ObjectSettingsForm(request.POST, instance=object)
        object.delete()
        messages.add_message(
            request,
            messages.SUCCESS,
            "Tracked Product Files Deleted.",
            extra_tags="alert-success",
        )
        return HttpResponseRedirect(reverse("view_objects", args=(pid,)))
    else:
        tform = DeleteObjectsSettingsForm(instance=object)

    product_tab = Product_Tab(
        pid, title="Delete Product Tool Configuration", tab="settings"
    )
    return render(
        request, "dojo/delete_object.html", {"tform": tform, "product_tab": product_tab}
    )


@user_passes_test(lambda u: u.is_staff)
def view_object_eng(request, id):
    object_queryset = Objects_Engagement.objects.filter(engagement=id).order_by(
        "object_id__path", "object_id__folder", "object_id__artifact"
    )
    engagement = Engagement.objects.get(id=id)
    product_tab = Product_Tab(
        engagement.product.id,
        title="Tracked Files, Folders and Artifacts on a Product",
        tab="engagements",
    )
    product_tab.setEngagement(engagement)
    return render(
        request,
        "dojo/view_objects_eng.html",
        {"object_queryset": object_queryset, "product_tab": product_tab, "id": id},
    )
