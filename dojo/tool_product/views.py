# #  product
import logging
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from dojo.forms import DeleteToolProductSettingsForm, ToolProductSettingsForm, NoteForm
from dojo.models import Product, Tool_Product_Settings
from django.http import HttpResponseRedirect
from dojo.utils import add_breadcrumb, Product_Tab

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_staff)
def new_tool_product(request, pid):
    prod = get_object_or_404(Product, id=pid)
    if request.method == "POST":
        tform = ToolProductSettingsForm(request.POST)
        if tform.is_valid():
            # form.tool_type = tool_type
            new_prod = tform.save(commit=False)
            new_prod.product = prod
            new_prod.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Product Tool Configuration Successfully Created.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("all_tool_product", args=(pid,)))
    else:
        tform = ToolProductSettingsForm()
    product_tab = Product_Tab(pid, title="Tool Configurations", tab="settings")
    return render(
        request,
        "dojo/new_tool_product.html",
        {"tform": tform, "product_tab": product_tab, "pid": pid},
    )


@user_passes_test(lambda u: u.is_staff)
def all_tool_product(request, pid):
    prod = get_object_or_404(Product, id=pid)
    tools = Tool_Product_Settings.objects.filter(product=prod).order_by("name")
    product_tab = Product_Tab(prod.id, title="Tool Configurations", tab="settings")
    return render(
        request,
        "dojo/view_tool_product_all.html",
        {"prod": prod, "tools": tools, "product_tab": product_tab},
    )


@user_passes_test(lambda u: u.is_staff)
def view_tool_product(request, pid, ttid):
    tool = Tool_Product_Settings.objects.get(pk=ttid)
    notes = tool.notes.all()

    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            tool.notes.add(new_note)
            form = NoteForm()
            # url = request.build_absolute_uri(reverse("view_test", args=(test.id,)))
            # title="Test: %s on %s" % (test.test_type.name, test.engagement.product.name)
            # process_notifications(request, new_note, url, title)
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        form = NoteForm()

    add_breadcrumb(
        title="View Product Tool Configuration", top_level=False, request=request
    )

    return render(
        request,
        "dojo/view_tool_product.html",
        {"tool": tool, "notes": notes, "form": form},
    )


@user_passes_test(lambda u: u.is_staff)
def edit_tool_product(request, pid, ttid):
    prod = get_object_or_404(Product, id=pid)
    tool_product = Tool_Product_Settings.objects.get(pk=ttid)

    if request.method == "POST":
        tform = ToolProductSettingsForm(request.POST, instance=tool_product)
        if tform.is_valid():
            tform.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Tool Product Configuration Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("all_tool_product", args=(pid,)))
    else:
        tform = ToolProductSettingsForm(instance=tool_product)

    product_tab = Product_Tab(
        pid, title="Edit Product Tool Configuration", tab="settings"
    )
    return render(
        request,
        "dojo/edit_tool_product.html",
        {"tform": tform, "product_tab": product_tab},
    )


@user_passes_test(lambda u: u.is_staff)
def delete_tool_product(request, pid, ttid):
    tool_product = Tool_Product_Settings.objects.get(pk=ttid)
    prod = get_object_or_404(Product, id=pid)
    if request.method == "POST":
        tform = DeleteToolProductSettingsForm(request.POST, instance=tool_product)
        tool_product.delete()
        messages.add_message(
            request,
            messages.SUCCESS,
            "Tool Product Successfully Deleted.",
            extra_tags="alert-success",
        )
        return HttpResponseRedirect(reverse("all_tool_product", args=(pid,)))
    else:
        tform = ToolProductSettingsForm(instance=tool_product)

    product_tab = Product_Tab(
        pid, title="Delete Product Tool Configuration", tab="settings"
    )

    return render(
        request,
        "dojo/delete_tool_product.html",
        {"tform": tform, "product_tab": product_tab},
    )


@user_passes_test(lambda u: u.is_staff)
def tool_product(request):
    confs = Tool_Product_Settings.objects.all().order_by("name")
    add_breadcrumb(
        title="Tool Configuration List", top_level=not len(request.GET), request=request
    )
    return render(
        request,
        "dojo/tool_product.html",
        {
            "confs": confs,
        },
    )
