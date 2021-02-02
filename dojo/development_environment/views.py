# #dev envs
import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from dojo.filters import DevelopmentEnvironmentFilter
from dojo.forms import Development_EnvironmentForm, Delete_Dev_EnvironmentForm
from dojo.models import Development_Environment
from dojo.utils import get_page_items, add_breadcrumb

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_staff)
def dev_env(request):
    initial_queryset = Development_Environment.objects.all().order_by("name")
    name_words = [de.name for de in initial_queryset]
    devs = DevelopmentEnvironmentFilter(request.GET, queryset=initial_queryset)
    dev_page = get_page_items(request, devs.qs, 25)
    add_breadcrumb(title="Environment List", top_level=True, request=request)
    return render(
        request,
        "dojo/dev_env.html",
        {
            "name": "Environment",
            "metric": False,
            "user": request.user,
            "devs": dev_page,
            "dts": devs,
            "name_words": name_words,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def add_dev_env(request):
    form = Development_EnvironmentForm()
    if request.method == "POST":
        form = Development_EnvironmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Environment added successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("dev_env"))
    add_breadcrumb(title="Add Environment", top_level=False, request=request)
    return render(
        request,
        "dojo/new_dev_env.html",
        {
            "name": "Add Environment",
            "metric": False,
            "user": request.user,
            "form": form,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def edit_dev_env(request, deid):
    de = get_object_or_404(Development_Environment, pk=deid)
    form1 = Development_EnvironmentForm(instance=de)
    form2 = Delete_Dev_EnvironmentForm(instance=de)
    if request.method == "POST" and request.POST.get("edit_dev_env"):
        form1 = Development_EnvironmentForm(request.POST, instance=de)
        if form1.is_valid():
            de = form1.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Environment updated successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("dev_env"))
    if request.method == "POST" and request.POST.get("delete_dev_env"):
        form2 = Delete_Dev_EnvironmentForm(request.POST, instance=de)
        if form2.is_valid():
            de.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Environment deleted successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("dev_env"))

    add_breadcrumb(title="Edit Environment", top_level=False, request=request)
    return render(
        request,
        "dojo/edit_dev_env.html",
        {
            "name": "Edit Environment",
            "metric": False,
            "user": request.user,
            "form1": form1,
            "de": de,
        },
    )
