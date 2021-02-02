# #  product
import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from dojo.models import Tool_Configuration
from dojo.utils import dojo_crypto_encrypt, prepare_for_view
from dojo.utils import add_breadcrumb
from dojo.forms import ToolConfigForm

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_staff)
def new_tool_config(request):
    if request.method == "POST":
        tform = ToolConfigForm(request.POST)
        if tform.is_valid():
            tform.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Tool Configuration Successfully Created.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse(
                    "tool_config",
                )
            )
    else:
        tform = ToolConfigForm()
        add_breadcrumb(title="New Tool Configuration", top_level=False, request=request)
    return render(request, "dojo/new_tool_config.html", {"tform": tform})


@user_passes_test(lambda u: u.is_staff)
def edit_tool_config(request, ttid):
    tool_config = Tool_Configuration.objects.get(pk=ttid)
    if request.method == "POST":
        tform = ToolConfigForm(request.POST, instance=tool_config)
        if tform.is_valid():
            form_copy = tform.save(commit=False)
            form_copy.password = dojo_crypto_encrypt(tform.cleaned_data["password"])
            form_copy.ssh = dojo_crypto_encrypt(tform.cleaned_data["ssh"])
            form_copy.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Tool Configuration Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse(
                    "tool_config",
                )
            )
    else:
        tool_config.password = prepare_for_view(tool_config.password)
        tool_config.ssh = prepare_for_view(tool_config.ssh)
        tform = ToolConfigForm(instance=tool_config)
    add_breadcrumb(title="Edit Tool Configuration", top_level=False, request=request)

    return render(
        request,
        "dojo/edit_tool_config.html",
        {
            "tform": tform,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def tool_config(request):
    confs = Tool_Configuration.objects.all().order_by("name")
    add_breadcrumb(
        title="Tool Configuration List", top_level=not len(request.GET), request=request
    )
    return render(
        request,
        "dojo/tool_config.html",
        {
            "confs": confs,
        },
    )
