# Standard library imports
import json
import logging

# Third party imports
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.utils import NestedObjects
from django.db import DEFAULT_DB_ALIAS

# Local application/library imports
from dojo.models import (
    Rule,
    System_Settings,
    Finding,
    Test,
    Test_Type,
    Engagement,
    Product,
    Product_Type,
    Child_Rule,
)
from dojo.forms import RuleFormSet, DeleteRuleForm, RuleForm
from dojo.utils import add_breadcrumb

logger = logging.getLogger(__name__)

# Fields for each model ruleset

finding_fields = [f.name for f in Finding._meta.fields]
test_fields = [f.name for f in Test._meta.fields]
test_type_fields = [f.name for f in Test_Type._meta.fields]
engagement_fields = [f.name for f in Engagement._meta.fields]
product_fields = [f.name for f in Product._meta.fields]
product_type_fields = [f.name for f in Product_Type._meta.fields]
field_dictionary = {}
field_dictionary["Finding"] = finding_fields
field_dictionary["Test Type"] = test_type_fields
field_dictionary["Test"] = test_fields
field_dictionary["Engagement"] = engagement_fields
field_dictionary["Product"] = product_fields
field_dictionary["Product Type"] = product_type_fields


def rules(request):
    initial_queryset = Rule.objects.all().order_by("name")
    add_breadcrumb(title="Rules", top_level=True, request=request)
    return render(
        request,
        "dojo/rules.html",
        {
            "name": "Rules List",
            "metric": False,
            "user": request.user,
            "rules": initial_queryset,
        },
    )


def new_rule(request):
    if request.method == "POST":
        form = RuleForm(request.POST)
        if form.is_valid():
            rule = form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Rule created successfully.",
                extra_tags="alert-success",
            )
            if "_Add Child" in request.POST:
                return HttpResponseRedirect(reverse("Add Child", args=(rule.id,)))
            return HttpResponseRedirect(reverse("rules"))
    form = RuleForm()
    add_breadcrumb(title="New Dojo Rule", top_level=False, request=request)
    return render(
        request,
        "dojo/new_rule2.html",
        {
            "form": form,
            "finding_fields": finding_fields,
            "test_fields": test_fields,
            "engagement_fields": engagement_fields,
            "product_fields": product_fields,
            "product_type_fields": product_type_fields,
            "field_dictionary": json.dumps(field_dictionary),
        },
    )


@user_passes_test(lambda u: u.is_staff)
def add_child(request, pid):
    rule = get_object_or_404(Rule, pk=pid)
    if request.method == "POST":
        forms = RuleFormSet(request.POST)
        for form in forms:
            if form.is_valid():
                cr = form.save(commit=False)
                cr.parent_rule = rule
                cr.save()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Rule created successfully.",
                    extra_tags="alert-success",
                )
                return HttpResponseRedirect(reverse("rules"))
    form = RuleFormSet(queryset=Child_Rule.objects.filter(parent_rule=rule))
    add_breadcrumb(title="New Dojo Rule", top_level=False, request=request)
    return render(
        request,
        "dojo/new_rule.html",
        {
            "form": form,
            "pid": pid,
            "finding_fields": finding_fields,
            "test_fields": test_fields,
            "engagement_fields": engagement_fields,
            "product_fields": product_fields,
            "product_type_fields": product_type_fields,
            "field_dictionary": json.dumps(field_dictionary),
        },
    )


@user_passes_test(lambda u: u.is_staff)
def edit_rule(request, pid):
    pt = get_object_or_404(Rule, pk=pid)
    children = Rule.objects.filter(parent_rule=pt)
    all_rules = children | Rule.objects.filter(pk=pid)
    form = RuleForm(instance=pt)
    if request.method == "POST":
        form = RuleForm(request.POST, instance=pt)
        if form.is_valid():
            pt = form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Rule updated successfully.",
                extra_tags="alert-success",
            )
            if "_Add Child" in request.POST:
                return HttpResponseRedirect(reverse("Add Child", args=(pt.id,)))
            return HttpResponseRedirect(reverse("rules"))
    add_breadcrumb(title="Edit Rule", top_level=False, request=request)
    return render(
        request,
        "dojo/edit_rule.html",
        {
            "name": "Edit Rule",
            "metric": False,
            "user": request.user,
            "form": form,
            "field_dictionary": json.dumps(field_dictionary),
            "pt": pt,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def delete_rule(request, tid):
    rule = get_object_or_404(Rule, pk=tid)
    form = DeleteRuleForm(instance=rule)

    if request.method == "POST":
        # print('id' in request.POST, file=sys.stderr)
        # print(str(rule.id) == request.POST['id'], file=sys.stderr)
        # print(str(rule.id) == request.POST['id'], file=sys.stderr)
        # if 'id' in request.POST and str(rule.id) == request.POST['id']:
        form = DeleteRuleForm(request.POST, instance=rule)
        # print(form.is_valid(), file=sys.stderr)
        # print(form.errors, file=sys.stderr)
        # print(form.non_field_errors(), file=sys.stderr)
        # print('id' in request.POST, file=sys.stderr)
        if form.is_valid():
            rule.delete()
            messages.add_message(
                request, messages.SUCCESS, "Rule deleted.", extra_tags="alert-success"
            )
            return HttpResponseRedirect(reverse("rules"))

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([rule])
    rels = collector.nested()

    add_breadcrumb(parent=rule, title="Delete", top_level=False, request=request)
    system_settings = System_Settings.objects.get()
    return render(
        request,
        "dojo/delete_rule.html",
        {
            "rule": rule,
            "form": form,
            "active_tab": "findings",
            "system_settings": system_settings,
            "rels": rels,
        },
    )
