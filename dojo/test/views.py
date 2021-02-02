# #  tests
import logging
import operator
import json
import httplib2
import base64
from datetime import datetime
import googleapiclient.discovery
from google.oauth2 import service_account
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db.models import Q, QuerySet, Count
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.utils import timezone
from django.contrib.admin.utils import NestedObjects
from django.db import DEFAULT_DB_ALIAS

from dojo.filters import TemplateFindingFilter, OpenFindingFilter
from dojo.forms import (
    NoteForm,
    TestForm,
    FindingForm,
    DeleteTestForm,
    AddFindingForm,
    TypedNoteForm,
    ImportScanForm,
    ReImportScanForm,
    JIRAFindingForm,
    JIRAImportScanForm,
    FindingBulkUpdateForm,
)
from dojo.models import (
    Finding,
    Test,
    Notes,
    Note_Type,
    BurpRawRequestResponse,
    Endpoint,
    Stub_Finding,
    Finding_Template,
    Cred_Mapping,
    Dojo_User,
    System_Settings,
    Endpoint_Status,
)
from dojo.tools.factory import import_parser_factory, get_choices
from dojo.utils import (
    get_page_items,
    get_page_items_and_count,
    add_breadcrumb,
    get_cal_event,
    message,
    process_notifications,
    get_system_setting,
    Product_Tab,
    max_safe,
    is_scan_file_too_large,
    get_words_for_field,
)
from dojo.notifications.helper import create_notification
from dojo.finding.views import find_available_notetypes
from functools import reduce
from dojo.user.helper import user_must_be_authorized
import dojo.jira_link.helper as jira_helper
import dojo.finding.helper as finding_helper
from django.views.decorators.vary import vary_on_cookie

logger = logging.getLogger(__name__)
parse_logger = logging.getLogger("dojo")
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


@user_must_be_authorized(Test, "view", "tid")
def view_test(request, tid):
    test = get_object_or_404(Test, pk=tid)
    prod = test.engagement.product
    notes = test.notes.all()
    note_type_activation = Note_Type.objects.filter(is_active=True).count()
    if note_type_activation:
        available_note_types = find_available_notetypes(notes)
    files = test.files.all()
    person = request.user.username
    findings = Finding.objects.filter(test=test).order_by("numerical_severity")
    findings = OpenFindingFilter(request.GET, queryset=findings)
    stub_findings = Stub_Finding.objects.filter(test=test)
    cred_test = (
        Cred_Mapping.objects.filter(test=test)
        .select_related("cred_id")
        .order_by("cred_id")
    )
    creds = (
        Cred_Mapping.objects.filter(engagement=test.engagement)
        .select_related("cred_id")
        .order_by("cred_id")
    )
    system_settings = get_object_or_404(System_Settings, id=1)
    if request.method == "POST" and request.user.is_staff:
        if note_type_activation:
            form = TypedNoteForm(
                request.POST, available_note_types=available_note_types
            )
        else:
            form = NoteForm(request.POST)
        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            test.notes.add(new_note)
            if note_type_activation:
                form = TypedNoteForm(available_note_types=available_note_types)
            else:
                form = NoteForm()
            url = request.build_absolute_uri(reverse("view_test", args=(test.id,)))
            title = "Test: %s on %s" % (
                test.test_type.name,
                test.engagement.product.name,
            )
            process_notifications(request, new_note, url, title)
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        if note_type_activation:
            form = TypedNoteForm(available_note_types=available_note_types)
        else:
            form = NoteForm()

    title_words = get_words_for_field(findings.qs, "title")
    component_words = get_words_for_field(findings.qs, "component_name")

    paged_findings, total_findings_count = get_page_items_and_count(
        request, prefetch_for_findings(findings.qs), 25
    )
    paged_stub_findings = get_page_items(request, stub_findings, 25)
    show_re_upload = any(
        test.test_type.name in code for code in ImportScanForm.SORTED_SCAN_TYPE_CHOICES
    )

    product_tab = Product_Tab(prod.id, title="Test", tab="engagements")
    product_tab.setEngagement(test.engagement)
    jira_project = jira_helper.get_jira_project(test)

    bulk_edit_form = FindingBulkUpdateForm(request.GET)

    google_sheets_enabled = system_settings.enable_google_sheets
    sheet_url = None
    if google_sheets_enabled:
        spreadsheet_name = (
            test.engagement.product.name
            + "-"
            + test.engagement.name
            + "-"
            + str(test.id)
        )
        system_settings = get_object_or_404(System_Settings, id=1)
        service_account_info = json.loads(system_settings.credentials)
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        try:
            drive_service = googleapiclient.discovery.build(
                "drive", "v3", credentials=credentials, cache_discovery=False
            )
            folder_id = system_settings.drive_folder_ID
            files = (
                drive_service.files()
                .list(
                    q="mimeType='application/vnd.google-apps.spreadsheet' and parents in '%s' and name='%s'"
                    % (folder_id, spreadsheet_name),
                    spaces="drive",
                    pageSize=10,
                    fields="files(id, name)",
                )
                .execute()
            )
        except googleapiclient.errors.HttpError:
            messages.add_message(
                request,
                messages.ERROR,
                "There is a problem with the Google Sheets Sync Configuration. Contact your system admin to solve the issue. Until fixed Google Shet Sync feature can not be used.",
                extra_tags="alert-danger",
            )
            google_sheets_enabled = False
        except httplib2.ServerNotFoundError:
            messages.add_message(
                request,
                messages.ERROR,
                "Unable to reach the Google Sheet API.",
                extra_tags="alert-danger",
            )
        else:
            spreadsheets = files.get("files")
            if len(spreadsheets) == 1:
                spreadsheetId = spreadsheets[0].get("id")
                sheet_url = "https://docs.google.com/spreadsheets/d/" + spreadsheetId
    return render(
        request,
        "dojo/view_test.html",
        {
            "test": test,
            "product_tab": product_tab,
            "findings": paged_findings,
            "filtered": findings,
            "findings_count": total_findings_count,
            "stub_findings": paged_stub_findings,
            "title_words": title_words,
            "component_words": component_words,
            "form": form,
            "notes": notes,
            "files": files,
            "person": person,
            "request": request,
            "show_re_upload": show_re_upload,
            "creds": creds,
            "cred_test": cred_test,
            "jira_project": jira_project,
            "show_export": google_sheets_enabled,
            "sheet_url": sheet_url,
            "bulk_edit_form": bulk_edit_form,
        },
    )


def prefetch_for_findings(findings):
    prefetched_findings = findings
    if isinstance(
        findings, QuerySet
    ):  # old code can arrive here with prods being a list because the query was already executed
        prefetched_findings = prefetched_findings.select_related("reporter")
        prefetched_findings = prefetched_findings.prefetch_related("jira_issue")
        prefetched_findings = prefetched_findings.prefetch_related("test__test_type")
        prefetched_findings = prefetched_findings.prefetch_related(
            "test__engagement__jira_project__jira_instance"
        )
        prefetched_findings = prefetched_findings.prefetch_related(
            "test__engagement__product__jira_project_set__jira_instance"
        )
        prefetched_findings = prefetched_findings.prefetch_related("found_by")
        prefetched_findings = prefetched_findings.prefetch_related(
            "risk_acceptance_set"
        )
        # we could try to prefetch only the latest note with SubQuery and OuterRef, but I'm getting that MySql doesn't support limits in subqueries.
        prefetched_findings = prefetched_findings.prefetch_related("notes")
        prefetched_findings = prefetched_findings.prefetch_related("tags")
        prefetched_findings = prefetched_findings.prefetch_related("endpoints")
        prefetched_findings = prefetched_findings.prefetch_related("endpoint_status")
        prefetched_findings = prefetched_findings.prefetch_related(
            "endpoint_status__endpoint"
        )
        prefetched_findings = prefetched_findings.annotate(
            active_endpoint_count=Count(
                "endpoint_status__id", filter=Q(endpoint_status__mitigated=False)
            )
        )
        prefetched_findings = prefetched_findings.annotate(
            mitigated_endpoint_count=Count(
                "endpoint_status__id", filter=Q(endpoint_status__mitigated=True)
            )
        )
        prefetched_findings = prefetched_findings.prefetch_related(
            "test__engagement__product__authorized_users"
        )
        prefetched_findings = prefetched_findings.prefetch_related(
            "test__engagement__product__prod_type__authorized_users"
        )
    else:
        logger.debug("unable to prefetch because query was already executed")

    return prefetched_findings


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Test, "change", "tid")
def edit_test(request, tid):
    test = get_object_or_404(Test, pk=tid)
    form = TestForm(instance=test)
    if request.method == "POST":
        form = TestForm(request.POST, instance=test)
        if form.is_valid():
            new_test = form.save()
            messages.add_message(
                request, messages.SUCCESS, "Test saved.", extra_tags="alert-success"
            )
            return HttpResponseRedirect(
                reverse("view_engagement", args=(test.engagement.id,))
            )

    form.initial["target_start"] = test.target_start.date()
    form.initial["target_end"] = test.target_end.date()
    form.initial["description"] = test.description

    product_tab = Product_Tab(
        test.engagement.product.id, title="Edit Test", tab="engagements"
    )
    product_tab.setEngagement(test.engagement)
    return render(
        request,
        "dojo/edit_test.html",
        {
            "test": test,
            "product_tab": product_tab,
            "form": form,
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Test, "delete", "tid")
def delete_test(request, tid):
    test = get_object_or_404(Test, pk=tid)
    eng = test.engagement
    form = DeleteTestForm(instance=test)

    if request.method == "POST":
        if "id" in request.POST and str(test.id) == request.POST["id"]:
            form = DeleteTestForm(request.POST, instance=test)
            if form.is_valid():
                test.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Test and relationships removed.",
                    extra_tags="alert-success",
                )
                create_notification(
                    event="other",
                    title="Deletion of %s" % test.title,
                    description='The test "%s" was deleted by %s'
                    % (test.title, request.user),
                    url=request.build_absolute_uri(
                        reverse("view_engagement", args=(eng.id,))
                    ),
                    recipients=[test.engagement.lead],
                    icon="exclamation-triangle",
                )
                return HttpResponseRedirect(reverse("view_engagement", args=(eng.id,)))

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([test])
    rels = collector.nested()

    product_tab = Product_Tab(
        test.engagement.product.id, title="Delete Test", tab="engagements"
    )
    product_tab.setEngagement(test.engagement)
    return render(
        request,
        "dojo/delete_test.html",
        {
            "test": test,
            "product_tab": product_tab,
            "form": form,
            "rels": rels,
            "deletable_objects": rels,
        },
    )


@user_passes_test(lambda u: u.is_staff)
@cache_page(60 * 5)  # cache for 5 minutes
@vary_on_cookie
def test_calendar(request):
    if "lead" not in request.GET or "0" in request.GET.getlist("lead"):
        tests = Test.objects.all()
    else:
        filters = []
        leads = request.GET.getlist("lead", "")
        if "-1" in request.GET.getlist("lead"):
            leads.remove("-1")
            filters.append(Q(lead__isnull=True))
        filters.append(Q(lead__in=leads))
        tests = Test.objects.filter(reduce(operator.or_, filters))

    tests = tests.prefetch_related("test_type", "lead", "engagement__product")

    add_breadcrumb(title="Test Calendar", top_level=True, request=request)
    return render(
        request,
        "dojo/calendar.html",
        {
            "caltype": "tests",
            "leads": request.GET.getlist("lead", ""),
            "tests": tests,
            "users": Dojo_User.objects.all(),
        },
    )


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Test, "staff", "tid")
def test_ics(request, tid):
    test = get_object_or_404(Test, id=tid)
    start_date = datetime.combine(test.target_start, datetime.min.time())
    end_date = datetime.combine(test.target_end, datetime.max.time())
    uid = "dojo_test_%d_%d_%d" % (
        test.id,
        test.engagement.id,
        test.engagement.product.id,
    )
    cal = get_cal_event(
        start_date,
        end_date,
        "Test: %s (%s)" % (test.test_type.name, test.engagement.product.name),
        "Set aside for test %s, on product %s.  Additional detail can be found at %s"
        % (
            test.test_type.name,
            test.engagement.product.name,
            request.build_absolute_uri((reverse("view_test", args=(test.id,)))),
        ),
        uid,
    )
    output = cal.serialize()
    response = HttpResponse(content=output)
    response["Content-Type"] = "text/calendar"
    response["Content-Disposition"] = (
        "attachment; filename=%s.ics" % test.test_type.name
    )
    return response


# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Test, "staff", "tid")
def add_findings(request, tid):
    test = Test.objects.get(id=tid)
    form_error = False
    jform = None
    form = AddFindingForm(initial={"date": timezone.now().date()}, req_resp=None)
    push_all_jira_issues = jira_helper.is_push_all_issues(test)
    use_jira = jira_helper.get_jira_project(test) is not None

    if request.method == "POST":
        form = AddFindingForm(request.POST, req_resp=None)
        if (
            form["active"].value() is False or form["verified"].value() is False
        ) and "jiraform-push_to_jira" in request.POST:
            error = ValidationError(
                "Findings must be active and verified to be pushed to JIRA",
                code="not_active_or_verified",
            )
            if form["active"].value() is False:
                form.add_error("active", error)
            if form["verified"].value() is False:
                form.add_error("verified", error)
            messages.add_message(
                request,
                messages.ERROR,
                "Findings must be active and verified to be pushed to JIRA",
                extra_tags="alert-danger",
            )
        if (
            form["severity"].value() == "Info"
            and "jiraform-push_to_jira" in request.POST
        ):
            error = ValidationError(
                "Findings with Informational severity cannot be pushed to JIRA.",
                code="info-severity-to-jira",
            )

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
            if jform:
                logger.debug(
                    "jform.jira_issue: %s", jform.cleaned_data.get("jira_issue")
                )
                logger.debug(
                    "jform.push_to_jira: %s", jform.cleaned_data.get("push_to_jira")
                )

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
            new_finding.save(dedupe_option=False, push_to_jira=False)
            for ep in form.cleaned_data["endpoints"]:
                eps, created = Endpoint_Status.objects.get_or_create(
                    finding=new_finding, endpoint=ep
                )
                ep.endpoint_status.add(eps)

                new_finding.endpoints.add(ep)
                new_finding.endpoint_status.add(eps)

            # Push to jira?
            push_to_jira = False
            jira_message = None
            if jform and jform.is_valid():
                # can't use helper as when push_all_jira_issues is True, the checkbox gets disabled and is always false
                # push_to_jira = jira_helper.is_push_to_jira(new_finding, jform.cleaned_data.get('push_to_jira'))
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

            new_finding.save(false_history=True, push_to_jira=push_to_jira)
            create_notification(
                event="other",
                title="Addition of %s" % new_finding.title,
                description='Finding "%s" was added by %s'
                % (new_finding.title, request.user),
                url=request.build_absolute_uri(
                    reverse("view_finding", args=(new_finding.id,))
                ),
                icon="exclamation-triangle",
            )

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

    product_tab = Product_Tab(
        test.engagement.product.id, title="Add Finding", tab="engagements"
    )
    product_tab.setEngagement(test.engagement)
    return render(
        request,
        "dojo/add_findings.html",
        {
            "form": form,
            "product_tab": product_tab,
            "test": test,
            "temp": False,
            "tid": tid,
            "form_error": form_error,
            "jform": jform,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def add_temp_finding(request, tid, fid):
    jform = None
    test = get_object_or_404(Test, id=tid)
    finding = get_object_or_404(Finding_Template, id=fid)
    findings = Finding_Template.objects.all()
    push_all_jira_issues = jira_helper.is_push_all_issues(finding)

    if jira_helper.get_jira_project(test):
        jform = JIRAFindingForm(
            push_all=jira_helper.is_push_all_issues(test),
            prefix="jiraform",
            jira_project=jira_helper.get_jira_project(test),
        )
    else:
        jform = None

    if request.method == "POST":
        form = FindingForm(request.POST, template=True, req_resp=None)
        if (form["active"].value() is False or form["false_p"].value()) and form[
            "duplicate"
        ].value() is False:
            closing_disabled = Note_Type.objects.filter(
                is_mandatory=True, is_active=True
            ).count()
            if closing_disabled != 0:
                error_inactive = ValidationError(
                    "Can not set a finding as inactive without adding all mandatory notes",
                    code="not_active_or_false_p_true",
                )
                error_false_p = ValidationError(
                    "Can not set a finding as false positive without adding all mandatory notes",
                    code="not_active_or_false_p_true",
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
        if form.is_valid():
            finding.last_used = timezone.now()
            finding.save()
            new_finding = form.save(commit=False)
            new_finding.test = test
            new_finding.reporter = request.user
            new_finding.numerical_severity = Finding.get_numerical_severity(
                new_finding.severity
            )
            new_finding.date = datetime.today()
            finding_helper.update_finding_status(new_finding, request.user)

            create_template = new_finding.is_template
            # is template always False now in favor of new model Finding_Template
            # no further action needed here since this is already adding from template.
            new_finding.is_template = False
            new_finding.save(dedupe_option=False, false_history=False)
            for ep in form.cleaned_data["endpoints"]:
                eps, created = Endpoint_Status.objects.get_or_create(
                    finding=new_finding, endpoint=ep
                )
                ep.endpoint_status.add(eps)

                new_finding.endpoints.add(ep)
                new_finding.endpoint_status.add(eps)
            new_finding.save(false_history=True)
            if "jiraform-push_to_jira" in request.POST:
                jform = JIRAFindingForm(
                    request.POST,
                    prefix="jiraform",
                    push_all=push_all_jira_issues,
                    jira_project=jira_helper.get_jira_project(test),
                )
                if jform.is_valid():
                    if jform.cleaned_data.get("push_to_jira"):
                        jira_helper.push_to_jira(new_finding)

            messages.add_message(
                request,
                messages.SUCCESS,
                "Finding from template added successfully.",
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

            return HttpResponseRedirect(reverse("view_test", args=(test.id,)))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "The form has errors, please correct them below.",
                extra_tags="alert-danger",
            )
    else:
        form = FindingForm(
            template=True,
            req_resp=None,
            initial={
                "active": False,
                "date": timezone.now().date(),
                "verified": False,
                "false_p": False,
                "duplicate": False,
                "out_of_scope": False,
                "title": finding.title,
                "description": finding.description,
                "cwe": finding.cwe,
                "severity": finding.severity,
                "mitigation": finding.mitigation,
                "impact": finding.impact,
                "references": finding.references,
                "numerical_severity": finding.numerical_severity,
            },
        )

    product_tab = Product_Tab(
        test.engagement.product.id, title="Add Finding", tab="engagements"
    )
    product_tab.setEngagement(test.engagement)
    return render(
        request,
        "dojo/add_findings.html",
        {
            "form": form,
            "product_tab": product_tab,
            "jform": jform,
            "findings": findings,
            "temp": True,
            "fid": finding.id,
            "tid": test.id,
            "test": test,
        },
    )


def search(request, tid):
    test = get_object_or_404(Test, id=tid)
    templates = Finding_Template.objects.all()
    templates = TemplateFindingFilter(request.GET, queryset=templates)
    paged_templates = get_page_items(request, templates.qs, 25)

    title_words = get_words_for_field(templates.qs, "title")

    add_breadcrumb(
        parent=test, title="Add From Template", top_level=False, request=request
    )
    return render(
        request,
        "dojo/templates.html",
        {
            "templates": paged_templates,
            "filtered": templates,
            "title_words": title_words,
            "tid": tid,
            "add_from_template": True,
        },
    )


# bulk update and delete are combined, so we can't have the nice user_must_be_authorized decorator (yet)
# @user_passes_test(lambda u: u.is_staff)
@user_must_be_authorized(Test, "staff", "tid")
def re_import_scan_results(request, tid):
    additional_message = (
        "When re-uploading a scan, any findings not found in original scan will be updated as "
        "mitigated.  The process attempts to identify the differences, however manual verification "
        "is highly recommended."
    )
    test = get_object_or_404(Test, id=tid)
    scan_type = test.test_type.name
    engagement = test.engagement
    form = ReImportScanForm(test=test)
    jform = None
    jira_project = jira_helper.get_jira_project(test)
    push_all_jira_issues = jira_helper.is_push_all_issues(test)

    # Decide if we need to present the Push to JIRA form
    if get_system_setting("enable_jira") and jira_project:
        jform = JIRAImportScanForm(push_all=push_all_jira_issues, prefix="jiraform")

    if request.method == "POST":
        form = ReImportScanForm(request.POST, request.FILES, test=test)
        if jira_project:
            jform = JIRAImportScanForm(
                request.POST, push_all=push_all_jira_issues, prefix="jiraform"
            )
        if form.is_valid() and (jform is None or jform.is_valid()):
            scan_date = form.cleaned_data["scan_date"]

            scan_date_time = datetime.combine(scan_date, timezone.now().time())
            if settings.USE_TZ:
                scan_date_time = timezone.make_aware(
                    scan_date_time, timezone.get_default_timezone()
                )

            min_sev = form.cleaned_data["minimum_severity"]
            file = request.FILES.get("file", None)
            active = form.cleaned_data["active"]
            verified = form.cleaned_data["verified"]
            tags = form.cleaned_data["tags"]
            if "version" in form.cleaned_data and form.cleaned_data["version"]:
                test.version = form.cleaned_data["version"]
            close_old_findings = form.cleaned_data.get("close_old_findings", True)
            # Tags are replaced, same behaviour as with django-tagging
            test.tags = tags
            if file and is_scan_file_too_large(file):
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Report file is too large. Maximum supported size is {} MB".format(
                        settings.SCAN_FILE_MAX_SIZE
                    ),
                    extra_tags="alert-danger",
                )
                return HttpResponseRedirect(
                    reverse("re_import_scan_results", args=(test.id,))
                )

            try:
                parser = import_parser_factory(
                    file, test, active, verified, scan_type=scan_type
                )
                parser_findings = parser.get_findings(file, test)
            except ValueError:
                raise Http404()
            except Exception as e:
                messages.add_message(
                    request,
                    messages.ERROR,
                    "An error has occurred in the parser, please see error "
                    "log for details.",
                    extra_tags="alert-danger",
                )
                parse_logger.exception(e)
                parse_logger.error("Error in parser: {}".format(str(e)))
                return HttpResponseRedirect(
                    reverse("re_import_scan_results", args=(test.id,))
                )

            try:
                items = parser_findings
                original_items = list(test.finding_set.all())
                new_items = []
                mitigated_count = 0
                finding_count = 0
                finding_added_count = 0
                reactivated_count = 0
                reactivated_items = []
                unchanged_count = 0
                unchanged_items = []

                # can't use helper as when push_all_jira_issues is True, the checkbox gets disabled and is always false
                # push_to_jira = jira_helper.is_push_to_jira(new_finding, jform.cleaned_data.get('push_to_jira'))
                push_to_jira = push_all_jira_issues or (
                    jform and jform.cleaned_data.get("push_to_jira")
                )

                logger.debug("starting reimport of %i items.", len(items))
                i = 0
                for item in items:
                    sev = item.severity
                    if sev == "Information" or sev == "Informational":
                        sev = "Info"
                        item.severity = sev

                    # existing findings may be from before we had component_name/version fields
                    component_name = (
                        item.component_name if hasattr(item, "component_name") else None
                    )
                    component_version = (
                        item.component_version
                        if hasattr(item, "component_version")
                        else None
                    )

                    # If it doesn't clear minimum severity, move on
                    if Finding.SEVERITIES[sev] > Finding.SEVERITIES[min_sev]:
                        continue

                    # Try to find the existing finding
                    # If it's Veracode or Arachni, then we consider the description for some
                    # reason...
                    from titlecase import titlecase

                    item.title = titlecase(item.title)
                    if scan_type == "Veracode Scan" or scan_type == "Arachni Scan":
                        findings = Finding.objects.filter(
                            title=item.title,
                            test__id=test.id,
                            severity=sev,
                            numerical_severity=Finding.get_numerical_severity(sev),
                            description=item.description,
                        )

                    else:
                        findings = Finding.objects.filter(
                            title=item.title,
                            test__id=test.id,
                            severity=sev,
                            numerical_severity=Finding.get_numerical_severity(sev),
                        )

                    # some parsers generate 1 finding for each vulnerable file for each vulnerability
                    # i.e
                    # #: title                     : sev : file_path
                    # 1: CVE-2020-1234 jquery      : 1   : /file1.jar
                    # 2: CVE-2020-1234 jquery      : 1   : /file2.jar
                    #
                    # if we don't filter on file_path, we would find 2 existing findings
                    # and the logic below will get confused and map all incoming findings
                    # from the reimport on the first finding
                    #
                    # for Anchore we fix this here, we may need a broader fix (and testcases)
                    # or we may need to change the matching logic here to use the same logic
                    # as the deduplication logic (hashcode fields)

                    if scan_type == "Anchore Engine Scan":
                        if item.file_path:
                            findings = findings.filter(file_path=item.file_path)

                    if findings:
                        finding = findings[0]
                        if finding.mitigated or finding.is_Mitigated:
                            logger.debug(
                                "%i: reactivating: %i:%s:%s:%s",
                                i,
                                finding.id,
                                finding,
                                finding.component_name,
                                finding.component_version,
                            )
                            # it was once fixed, but now back
                            finding.mitigated = None
                            finding.is_Mitigated = False
                            finding.mitigated_by = None
                            finding.active = True
                            finding.verified = verified

                            # existing findings may be from before we had component_name/version fields
                            finding.component_name = (
                                finding.component_name
                                if finding.component_name
                                else component_name
                            )
                            finding.component_version = (
                                finding.component_version
                                if finding.component_version
                                else component_version
                            )

                            # don't run dedupe when reactivating
                            finding.save(dedupe_option=False)
                            note = Notes(
                                entry="Re-activated by %s re-upload." % scan_type,
                                author=request.user,
                            )
                            note.save()
                            finding.notes.add(note)

                            endpoint_status = finding.endpoint_status.all()
                            for status in endpoint_status:
                                status.mitigated_by = None
                                status.mitigated_time = None
                                status.mitigated = False
                                status.last_modified = timezone.now()
                                status.save()

                            reactivated_items.append(finding)
                            reactivated_count += 1
                        else:
                            # existing findings may be from before we had component_name/version fields
                            logger.debug(
                                "%i: updating existing finding: %i:%s:%s:%s",
                                i,
                                finding.id,
                                finding,
                                finding.component_name,
                                finding.component_version,
                            )
                            if (
                                not finding.component_name
                                or not finding.component_version
                            ):
                                finding.component_name = (
                                    finding.component_name
                                    if finding.component_name
                                    else component_name
                                )
                                finding.component_version = (
                                    finding.component_version
                                    if finding.component_version
                                    else component_version
                                )
                                finding.save(dedupe_option=False)
                            unchanged_items.append(finding)
                            unchanged_count += 1

                    else:
                        item.test = test
                        item.reporter = request.user
                        item.last_reviewed = timezone.now()
                        item.last_reviewed_by = request.user
                        item.verified = verified
                        item.active = active

                        # Save it. Don't dedupe before endpoints are added.
                        item.save(dedupe_option=False)
                        logger.debug(
                            "%i: creating new finding: %i:%s:%s:%s",
                            i,
                            item.id,
                            item,
                            item.component_name,
                            item.component_version,
                        )
                        deduplicationLogger.debug(
                            "reimport found multiple identical existing findings for %i, a non-exact match. these are ignored and a new finding has been created",
                            item.id,
                        )
                        finding_added_count += 1
                        # Add it to the new items
                        new_items.append(item)
                        finding = item

                        if (
                            hasattr(item, "unsaved_req_resp")
                            and len(item.unsaved_req_resp) > 0
                        ):
                            for req_resp in item.unsaved_req_resp:
                                if scan_type == "Arachni Scan":
                                    burp_rr = BurpRawRequestResponse(
                                        finding=item,
                                        burpRequestBase64=req_resp["req"],
                                        burpResponseBase64=req_resp["resp"],
                                    )
                                else:
                                    burp_rr = BurpRawRequestResponse(
                                        finding=item,
                                        burpRequestBase64=base64.b64encode(
                                            req_resp["req"].encode("utf-8")
                                        ),
                                        burpResponseBase64=base64.b64encode(
                                            req_resp["resp"].encode("utf-8")
                                        ),
                                    )
                                burp_rr.clean()
                                burp_rr.save()

                        if (
                            item.unsaved_request is not None
                            and item.unsaved_response is not None
                        ):
                            burp_rr = BurpRawRequestResponse(
                                finding=finding,
                                burpRequestBase64=base64.b64encode(
                                    item.unsaved_request.encode()
                                ),
                                burpResponseBase64=base64.b64encode(
                                    item.unsaved_response.encode()
                                ),
                            )
                            burp_rr.clean()
                            burp_rr.save()

                    if finding:
                        finding_count += 1
                        for endpoint in item.unsaved_endpoints:
                            from django.core.exceptions import MultipleObjectsReturned

                            try:
                                ep, created = Endpoint.objects.get_or_create(
                                    protocol=endpoint.protocol,
                                    host=endpoint.host,
                                    path=endpoint.path,
                                    query=endpoint.query,
                                    fragment=endpoint.fragment,
                                    product=test.engagement.product,
                                )
                                eps, created = Endpoint_Status.objects.get_or_create(
                                    finding=finding, endpoint=ep
                                )
                                ep.endpoint_status.add(eps)

                                finding.endpoints.add(ep)
                                finding.endpoint_status.add(eps)
                            except (MultipleObjectsReturned):
                                pass
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
                                finding=finding, endpoint=ep
                            )
                            ep.endpoint_status.add(eps)

                            finding.endpoints.add(ep)
                            finding.endpoint_status.add(eps)
                        if item.unsaved_tags is not None:
                            finding.tags = item.unsaved_tags

                    # Save it. This may be the second time we save it in this function.
                    finding.save(push_to_jira=push_to_jira)
                    i += 1
                # calculate the difference
                to_mitigate = (
                    set(original_items) - set(reactivated_items) - set(unchanged_items)
                )
                mitigated_findings = []
                if close_old_findings:
                    for finding in to_mitigate:
                        # finding = Finding.objects.get(id=finding_id)
                        if not finding.mitigated or not finding.is_Mitigated:
                            logger.debug(
                                "mitigating finding: %i:%s", finding.id, finding
                            )
                            finding.mitigated = scan_date_time
                            finding.is_Mitigated = True
                            finding.mitigated_by = request.user
                            finding.active = False

                            # if we're mitigating a finding, we don't want to run dedupe
                            # finding.save(push_to_jira=push_to_jira)
                            finding.save(push_to_jira=push_to_jira, dedupe_option=False)
                            note = Notes(
                                entry="Mitigated by %s re-upload." % scan_type,
                                author=request.user,
                            )
                            note.save()
                            finding.notes.add(note)
                            mitigated_findings.append(finding)
                            mitigated_count += 1

                            endpoint_status = finding.endpoint_status.all()
                            for status in endpoint_status:
                                status.mitigated_by = request.user
                                status.mitigated_time = timezone.now()
                                status.mitigated = True
                                status.last_modified = timezone.now()
                                status.save()

                untouched = set(unchanged_items) - set(to_mitigate)

                test.updated = max_safe([scan_date_time, test.updated])
                test.engagement.updated = max_safe(
                    [scan_date_time, test.engagement.updated]
                )

                test.save()
                test.engagement.save()

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "%s processed, a total of " % scan_type
                    + message(finding_count, "finding", "processed"),
                    extra_tags="alert-success",
                )
                if finding_added_count > 0:
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "A total of "
                        + message(finding_added_count, "finding", "added")
                        + ", that are new to scan.",
                        extra_tags="alert-success",
                    )
                if reactivated_count > 0:
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "A total of "
                        + message(reactivated_count, "finding", "reactivated")
                        + ", that are back in scan results.",
                        extra_tags="alert-success",
                    )
                if mitigated_count > 0:
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "A total of "
                        + message(mitigated_count, "finding", "mitigated")
                        + ". Please manually verify each one.",
                        extra_tags="alert-success",
                    )

                # create_notification(event='scan_added', title=str(finding_count) + " findings for " + test.engagement.product.name, finding_count=finding_count, test=test, engagement=test.engagement, url=reverse('view_test', args=(test.id,)))

                updated_count = mitigated_count + reactivated_count + len(new_items)
                if updated_count > 0:
                    # new_items = original_items
                    title = (
                        "Updated "
                        + str(updated_count)
                        + " findings for "
                        + str(test.engagement.product)
                        + ": "
                        + str(test.engagement.name)
                        + ": "
                        + str(test)
                    )
                    create_notification(
                        event="scan_added",
                        title=title,
                        findings_new=new_items,
                        findings_mitigated=mitigated_findings,
                        findings_reactivated=reactivated_items,
                        finding_count=updated_count,
                        test=test,
                        engagement=test.engagement,
                        product=test.engagement.product,
                        findings_untouched=untouched,
                        url=reverse("view_test", args=(test.id,)),
                    )
                else:
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "No findings were added/updated/closed/reactivated as the findings in Defect Dojo are identical to those in the uploaded report.",
                        extra_tags="alert-success",
                    )

                return HttpResponseRedirect(reverse("view_test", args=(test.id,)))
            except SyntaxError:
                messages.add_message(
                    request,
                    messages.ERROR,
                    "There appears to be an error in the XML report, please check and try again.",
                    extra_tags="alert-danger",
                )

    product_tab = Product_Tab(
        engagement.product.id, title="Re-upload a %s" % scan_type, tab="engagements"
    )
    product_tab.setEngagement(engagement)
    form.fields["endpoints"].queryset = Endpoint.objects.filter(
        product__id=product_tab.product.id
    )
    return render(
        request,
        "dojo/import_scan_results.html",
        {
            "form": form,
            "product_tab": product_tab,
            "eid": engagement.id,
            "additional_message": additional_message,
            "jform": jform,
            "scan_types": get_choices(),
        },
    )
