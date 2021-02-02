from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from django.db import IntegrityError
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg2 import openapi
from drf_yasg2.utils import swagger_auto_schema, no_body
import base64
from dojo.engagement.services import close_engagement, reopen_engagement
from dojo.models import (
    Product,
    Product_Type,
    Engagement,
    Test,
    Test_Type,
    Finding,
    User,
    ScanSettings,
    Scan,
    Stub_Finding,
    Finding_Template,
    Notes,
    JIRA_Issue,
    Tool_Product_Settings,
    Tool_Configuration,
    Tool_Type,
    Endpoint,
    JIRA_Project,
    JIRA_Instance,
    DojoMeta,
    Development_Environment,
    Dojo_User,
    Note_Type,
    System_Settings,
    App_Analysis,
    Endpoint_Status,
    Sonarqube_Issue,
    Sonarqube_Issue_Transition,
    Sonarqube_Product,
    Regulation,
    BurpRawRequestResponse,
    FileUpload,
)

from dojo.endpoint.views import get_endpoint_ids
from dojo.reports.views import report_url_resolver, prefetch_related_findings_for_report
from dojo.finding.views import (
    set_finding_as_original_internal,
    reset_finding_duplicate_status_internal,
    duplicate_cluster,
)
from dojo.filters import (
    ReportFindingFilter,
    ReportAuthedFindingFilter,
    ApiFindingFilter,
    ApiProductFilter,
    ApiEngagementFilter,
    ApiEndpointFilter,
    ApiAppAnalysisFilter,
    ApiTestFilter,
    ApiTemplateFindingFilter,
)
from dojo.risk_acceptance import api as ra_api
from dateutil.relativedelta import relativedelta
from django.conf import settings
from datetime import datetime
from dojo.utils import get_period_counts_legacy, get_system_setting
from dojo.api_v2 import serializers, permissions, prefetch, schema
from django.db.models import Count, Q
import dojo.jira_link.helper as jira_helper
import logging
import tagulous

logger = logging.getLogger(__name__)


class EndPointViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.EndpointSerializer
    queryset = Endpoint.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_class = ApiEndpointFilter

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Endpoint.objects.filter(
                Q(product__authorized_users__in=[self.request.user])
                | Q(product__prod_type__authorized_users__in=[self.request.user])
            )
        else:
            return Endpoint.objects.all()

    @swagger_auto_schema(
        request_body=serializers.ReportGenerateOptionSerializer,
        responses={status.HTTP_200_OK: serializers.ReportGenerateSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.UserHasReportGeneratePermission],
    )
    def generate_report(self, request, pk=None):
        endpoint = get_object_or_404(Endpoint.objects, id=pk)

        options = {}
        # prepare post data
        report_options = serializers.ReportGenerateOptionSerializer(data=request.data)
        if report_options.is_valid():
            options["include_finding_notes"] = report_options.validated_data[
                "include_finding_notes"
            ]
            options["include_finding_images"] = report_options.validated_data[
                "include_finding_images"
            ]
            options["include_executive_summary"] = report_options.validated_data[
                "include_executive_summary"
            ]
            options["include_table_of_contents"] = report_options.validated_data[
                "include_table_of_contents"
            ]
        else:
            return Response(report_options.errors, status=status.HTTP_400_BAD_REQUEST)

        data = report_generate(request, endpoint, options)
        report = serializers.ReportGenerateSerializer(data)
        return Response(report.data)


class EndpointStatusViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.EndpointStatusSerializer
    queryset = Endpoint_Status.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "mitigated",
        "false_positive",
        "out_of_scope",
        "risk_accepted",
        "mitigated_by",
        "finding",
        "endpoint",
    )


class EngagementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    ra_api.AcceptedRisksMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.EngagementSerializer
    queryset = Engagement.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_class = ApiEngagementFilter

    @property
    def risk_application_model_class(self):
        return Engagement

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Engagement.objects.filter(
                Q(product__authorized_users__in=[self.request.user])
                | Q(product__prod_type__authorized_users__in=[self.request.user])
            )
        else:
            return Engagement.objects.all()

    @swagger_auto_schema(request_body=no_body, responses={status.HTTP_200_OK: ""})
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        eng = get_object_or_404(Engagement.objects, id=pk)
        close_engagement(eng)
        return HttpResponse()

    @swagger_auto_schema(request_body=no_body, responses={status.HTTP_200_OK: ""})
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        eng = get_object_or_404(Engagement.objects, id=pk)
        reopen_engagement(eng)
        return HttpResponse()

    @swagger_auto_schema(
        request_body=serializers.ReportGenerateOptionSerializer,
        responses={status.HTTP_200_OK: serializers.ReportGenerateSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.UserHasReportGeneratePermission],
    )
    def generate_report(self, request, pk=None):
        engagement = get_object_or_404(Engagement.objects, id=pk)

        options = {}
        # prepare post data
        report_options = serializers.ReportGenerateOptionSerializer(data=request.data)
        if report_options.is_valid():
            options["include_finding_notes"] = report_options.validated_data[
                "include_finding_notes"
            ]
            options["include_finding_images"] = report_options.validated_data[
                "include_finding_images"
            ]
            options["include_executive_summary"] = report_options.validated_data[
                "include_executive_summary"
            ]
            options["include_table_of_contents"] = report_options.validated_data[
                "include_table_of_contents"
            ]
        else:
            return Response(report_options.errors, status=status.HTTP_400_BAD_REQUEST)

        data = report_generate(request, engagement, options)
        report = serializers.ReportGenerateSerializer(data)
        return Response(report.data)

    @action(detail=True, methods=["get", "post", "patch"])
    def notes(self, request, pk=None):
        engagement = get_object_or_404(Engagement.objects, id=pk)
        if request.method == "POST":
            new_note = serializers.AddNewNoteOptionSerializer(data=request.data)
            if new_note.is_valid():
                entry = new_note.validated_data["entry"]
                private = new_note.validated_data["private"]
                note_type = new_note.validated_data["note_type"]
            else:
                return Response(new_note.errors, status=status.HTTP_400_BAD_REQUEST)

            author = request.user
            note = Notes(
                entry=entry, author=author, private=private, note_type=note_type
            )
            note.save()
            engagement.notes.add(note)

            serialized_note = serializers.NoteSerializer(
                {"author": author, "entry": entry, "private": private}
            )
            result = serializers.EngagementToNotesSerializer(
                {"engagement_id": engagement, "notes": [serialized_note.data]}
            )
            return Response(serialized_note.data, status=status.HTTP_200_OK)
        notes = engagement.notes.all()

        serialized_notes = []
        if notes:
            serialized_notes = serializers.EngagementToNotesSerializer(
                {"engagement_id": engagement, "notes": notes}
            )
            return Response(serialized_notes.data, status=status.HTTP_200_OK)

        return Response(serialized_notes, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        method="get",
        responses={status.HTTP_200_OK: serializers.EngagementToFilesSerializer},
    )
    @swagger_auto_schema(
        methods=["post", "patch"],
        request_body=serializers.AddNewFileOptionSerializer,
        responses={status.HTTP_200_OK: serializers.FileSerializer},
    )
    @action(detail=True, methods=["get", "post", "patch"])
    def files(self, request, pk=None):
        engagement = get_object_or_404(Engagement.objects, id=pk)
        if request.method == "POST":
            new_file = serializers.FileSerializer(data=request.data)
            if new_file.is_valid():
                title = new_file.validated_data["title"]
                file = new_file.validated_data["file"]
            else:
                return Response(new_file.errors, status=status.HTTP_400_BAD_REQUEST)

            file = FileUpload(title=title, file=file)
            file.save()
            engagement.files.add(file)

            serialized_file = serializers.FileSerializer(
                {
                    "title": title,
                    "file": file,
                }
            )
            result = serializers.EngagementToFilesSerializer(
                {"engagement_id": engagement, "files": [serialized_file.data]}
            )
            return Response(serialized_file.data, status=status.HTTP_200_OK)
        files = engagement.files.all()

        serialized_files = []
        if files:
            serialized_files = serializers.EngagementToFilesSerializer(
                {"engagement_id": engagement, "files": files}
            )
            return Response(serialized_files.data, status=status.HTTP_200_OK)

        return Response(serialized_files, status=status.HTTP_200_OK)


class AppAnalysisViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.AppAnalysisSerializer
    queryset = App_Analysis.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_class = ApiAppAnalysisFilter


class FindingTemplatesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.FindingTemplateSerializer
    queryset = Finding_Template.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_class = ApiTemplateFindingFilter

    # def get_queryset(self):
    #     if not self.request.user.is_staff:
    #         return Finding_Template.objects.filter(
    #             id__in=[self.request.user])
    #     else:
    #         return Finding_Template.objects.all()


def _finding_related_fields_decorator():
    return swagger_auto_schema(
        responses={status.HTTP_200_OK: serializers.FindingSerializer},
        manual_parameters=[
            openapi.Parameter(
                name="related_fields",
                in_=openapi.IN_QUERY,
                description="Expand finding external relations (engagement, environment, product, product_type, test, test_type)",
                type=openapi.TYPE_BOOLEAN,
            )
        ],
    )


class FindingViewSet(
    prefetch.PrefetchListMixin,
    prefetch.PrefetchRetrieveMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    ra_api.AcceptedFindingsMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.FindingSerializer
    queryset = Finding.objects.all().prefetch_related(
        "endpoints",
        "reviewers",
        "images",
        "found_by",
        "notes",
        "risk_acceptance_set",
        "test",
        "test__test_type",
        "test__engagement",
        "test__environment",
        "test__engagement__product",
        "test__engagement__product__prod_type",
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ApiFindingFilter

    _related_field_parameters = [
        openapi.Parameter(
            name="related_fields",
            in_=openapi.IN_QUERY,
            description="Expand finding external relations (engagement, environment, product, product_type, test, test_type)",
            type=openapi.TYPE_BOOLEAN,
        )
    ]
    swagger_schema = (
        prefetch.get_prefetch_schema(
            ["findings_list", "findings_read"], serializers.FindingSerializer
        )
        .composeWith(schema.ExtraParameters("findings_list", _related_field_parameters))
        .composeWith(schema.ExtraParameters("findings_read", _related_field_parameters))
        .to_schema()
    )

    # Overriding mixins.UpdateModeMixin perform_update() method to grab push_to_jira
    # data and add that as a parameter to .save()
    def perform_update(self, serializer):
        # IF JIRA is enabled and this product has a JIRA configuration
        push_to_jira = serializer.validated_data.get("push_to_jira")
        jira_project = jira_helper.get_jira_project(serializer.instance)
        if get_system_setting("enable_jira") and jira_project:
            push_to_jira = push_to_jira or jira_project.push_all_issues

        serializer.save(push_to_jira=push_to_jira)

    def get_queryset(self):
        if not self.request.user.is_staff:
            findings = Finding.objects.filter(
                Q(test__engagement__product__authorized_users__in=[self.request.user])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        self.request.user
                    ]
                )
            )
        else:
            findings = Finding.objects.all()
        return findings.prefetch_related(
            "endpoints",
            "reviewers",
            "images",
            "found_by",
            "notes",
            "risk_acceptance_set",
            "test",
            "test__test_type",
            "test__engagement",
            "test__environment",
            "test__engagement__product",
            "test__engagement__product__prod_type",
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return serializers.FindingCreateSerializer
        else:
            return serializers.FindingSerializer

    @swagger_auto_schema(
        method="get", responses={status.HTTP_200_OK: serializers.TagSerializer}
    )
    @swagger_auto_schema(
        method="post",
        request_body=serializers.TagSerializer,
        responses={status.HTTP_200_OK: serializers.TagSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def tags(self, request, pk=None):
        finding = get_object_or_404(Finding.objects, id=pk)

        if request.method == "POST":
            new_tags = serializers.TagSerializer(data=request.data)
            if new_tags.is_valid():
                all_tags = finding.tags
                all_tags = serializers.TagSerializer({"tags": all_tags}).data["tags"]

                for tag in tagulous.utils.parse_tags(new_tags.validated_data["tags"]):
                    if tag not in all_tags:
                        all_tags.append(tag)
                new_tags = tagulous.utils.render_tags(all_tags)
                finding.tags = new_tags
                finding.save()
            else:
                return Response(new_tags.errors, status=status.HTTP_400_BAD_REQUEST)
        tags = finding.tags
        serialized_tags = serializers.TagSerializer({"tags": tags})
        return Response(serialized_tags.data)

    @swagger_auto_schema(
        method="get",
        responses={status.HTTP_200_OK: serializers.BurpRawRequestResponseSerializer},
    )
    @swagger_auto_schema(
        method="post",
        request_body=serializers.BurpRawRequestResponseSerializer,
        responses={status.HTTP_200_OK: serializers.BurpRawRequestResponseSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def request_response(self, request, pk=None):
        finding = get_object_or_404(Finding.objects, id=pk)

        if request.method == "POST":
            burps = serializers.BurpRawRequestResponseSerializer(
                data=request.data, many=isinstance(request.data, list)
            )
            if burps.is_valid():
                for pair in burps.validated_data["req_resp"]:
                    burp_rr = BurpRawRequestResponse(
                        finding=finding,
                        burpRequestBase64=base64.b64encode(
                            pair["request"].encode("utf-8")
                        ),
                        burpResponseBase64=base64.b64encode(
                            pair["response"].encode("utf-8")
                        ),
                    )
                    burp_rr.clean()
                    burp_rr.save()
            else:
                return Response(burps.errors, status=status.HTTP_400_BAD_REQUEST)

        burp_req_resp = BurpRawRequestResponse.objects.filter(finding=finding)
        burp_list = []
        for burp in burp_req_resp:
            request = burp.get_request()
            response = burp.get_response()
            burp_list.append({"request": request, "response": response})
        serialized_burps = serializers.BurpRawRequestResponseSerializer(
            {"req_resp": burp_list}
        )
        return Response(serialized_burps.data)

    @swagger_auto_schema(
        method="get",
        responses={status.HTTP_200_OK: serializers.FindingToNotesSerializer},
    )
    @swagger_auto_schema(
        methods=["post", "patch"],
        request_body=serializers.AddNewNoteOptionSerializer,
        responses={status.HTTP_200_OK: serializers.NoteSerializer},
    )
    @action(detail=True, methods=["get", "post", "patch"])
    def notes(self, request, pk=None):
        finding = get_object_or_404(Finding.objects, id=pk)
        if request.method == "POST":
            new_note = serializers.AddNewNoteOptionSerializer(data=request.data)
            if new_note.is_valid():
                entry = new_note.validated_data["entry"]
                private = (
                    new_note.validated_data["private"]
                    if "private" in new_note.validated_data
                    else False
                )
                note_type = (
                    new_note.validated_data["note_type"]
                    if "note_type" in new_note.validated_data
                    else None
                )
            else:
                return Response(new_note.errors, status=status.HTTP_400_BAD_REQUEST)

            author = request.user
            note = Notes(
                entry=entry, author=author, private=private, note_type=note_type
            )
            note.save()
            finding.notes.add(note)

            if finding.has_jira_issue:
                jira_helper.add_comment(finding, note)

            serialized_note = serializers.NoteSerializer(
                {"author": author, "entry": entry, "private": private}
            )
            result = serializers.FindingToNotesSerializer(
                {"finding_id": finding, "notes": [serialized_note.data]}
            )
            return Response(serialized_note.data, status=status.HTTP_200_OK)
        notes = finding.notes.all()

        serialized_notes = []
        if notes:
            serialized_notes = serializers.FindingToNotesSerializer(
                {"finding_id": finding, "notes": notes}
            )
            return Response(serialized_notes.data, status=status.HTTP_200_OK)

        return Response(serialized_notes, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        method="get",
        responses={status.HTTP_200_OK: serializers.FindingToFilesSerializer},
    )
    @swagger_auto_schema(
        methods=["post", "patch"],
        request_body=serializers.AddNewFileOptionSerializer,
        responses={status.HTTP_200_OK: serializers.FindingToFilesSerializer},
    )
    @action(detail=True, methods=["get", "post", "patch"])
    def files(self, request, pk=None):
        finding = get_object_or_404(Finding.objects, id=pk)
        if request.method == "POST":
            new_file = serializers.FileSerializer(data=request.data)
            if new_file.is_valid():
                title = new_file.validated_data["title"]
                file = new_file.validated_data["file"]
            else:
                return Response(new_file.errors, status=status.HTTP_400_BAD_REQUEST)

            file = FileUpload(title=title, file=file)
            file.save()
            finding.files.add(file)

            serialized_file = serializers.FileSerializer(
                {
                    "title": title,
                    "file": file,
                }
            )
            result = serializers.FindingToFilesSerializer(
                {"finding_id": finding, "files": [serialized_file.data]}
            )
            return Response(serialized_file.data, status=status.HTTP_200_OK)
        files = finding.files.all()

        serialized_files = []
        if files:
            serialized_files = serializers.FindingToFilesSerializer(
                {"finding_id": finding, "files": files}
            )
            return Response(serialized_files.data, status=status.HTTP_200_OK)

        return Response(serialized_files, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=serializers.FindingNoteSerializer,
        responses={status.HTTP_200_OK: ""},
    )
    @action(detail=True, methods=["patch"])
    def remove_note(self, request, pk=None):
        """Remove Note From Finding Note"""
        finding = get_object_or_404(Finding.objects, id=pk)
        notes = finding.notes.all()
        if request.data["note_id"]:
            note = get_object_or_404(Notes.objects, id=request.data["note_id"])
            if note not in notes:
                return Response(
                    {"error": "Selected Note is not assigned to this Finding"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"error": "('note_id') parameter missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if note.author.username == request.user.username or request.user.is_staff:
            finding.notes.remove(note)
            note.delete()
        else:
            return Response(
                {"error": "Delete Failed, You are not the Note's author"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"Success": "Selected Note has been Removed successfully"},
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        responses={status.HTTP_200_OK: ""},
        methods=["put", "patch"],
        request_body=serializers.TagSerializer,
    )
    @action(detail=True, methods=["put", "patch"])
    def remove_tags(self, request, pk=None):
        """ Remove Tag(s) from finding list of tags """
        finding = get_object_or_404(Finding.objects, id=pk)
        delete_tags = serializers.TagSerializer(data=request.data)
        if delete_tags.is_valid():
            all_tags = finding.tags
            all_tags = serializers.TagSerializer({"tags": all_tags}).data["tags"]

            # serializer turns it into a string, but we need a list
            del_tags = tagulous.utils.parse_tags(delete_tags.validated_data["tags"])
            if len(del_tags) < 1:
                return Response(
                    {"error": "Empty Tag List Not Allowed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for tag in del_tags:
                if tag not in all_tags:
                    return Response(
                        {"error": "'{}' is not a valid tag in list".format(tag)},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                all_tags.remove(tag)
            new_tags = tagulous.utils.render_tags(all_tags)
            finding.tags = new_tags
            finding.save()
            return Response({"success": "Tag(s) Removed"}, status=status.HTTP_200_OK)
        else:
            return Response(delete_tags.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={status.HTTP_200_OK: serializers.FindingSerializer(many=True)}
    )
    @action(detail=True, methods=["get"], url_path=r"duplicate")
    def get_duplicate_status(self, request, pk):
        finding = get_object_or_404(Finding, id=pk)
        result = duplicate_cluster(request, finding)
        serializer = serializers.FindingSerializer(
            instance=result, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={status.HTTP_200_OK: ""}, request_body=no_body)
    @action(detail=True, methods=["post"], url_path=r"duplicate/reset")
    def reset_finding_duplicate_status(self, request, pk):
        checked_duplicate_id = reset_finding_duplicate_status_internal(request.user, pk)
        if checked_duplicate_id is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={status.HTTP_200_OK: ""}, request_body=no_body)
    @action(detail=True, methods=["post"], url_path=r"original/(?P<new_fid>\d+)")
    def set_finding_as_original(self, request, pk, new_fid):
        success = set_finding_as_original_internal(request.user, pk, new_fid)
        if not success:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=serializers.ReportGenerateOptionSerializer,
        responses={status.HTTP_200_OK: serializers.ReportGenerateSerializer},
    )
    @action(detail=False, methods=["post"])
    def generate_report(self, request):
        findings = Finding.objects.all()
        options = {}
        # prepare post data
        report_options = serializers.ReportGenerateOptionSerializer(data=request.data)
        if report_options.is_valid():
            options["include_finding_notes"] = report_options.validated_data[
                "include_finding_notes"
            ]
            options["include_finding_images"] = report_options.validated_data[
                "include_finding_images"
            ]
            options["include_executive_summary"] = report_options.validated_data[
                "include_executive_summary"
            ]
            options["include_table_of_contents"] = report_options.validated_data[
                "include_table_of_contents"
            ]
        else:
            return Response(report_options.errors, status=status.HTTP_400_BAD_REQUEST)

        data = report_generate(request, findings, options)
        report = serializers.ReportGenerateSerializer(data)
        return Response(report.data)

    def _get_metadata(self, request, finding):
        metadata = DojoMeta.objects.filter(finding=finding)
        serializer = serializers.FindingMetaSerializer(instance=metadata, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _edit_metadata(self, request, finding):
        metadata_name = request.query_params.get("name", None)
        if metadata_name is None:
            return Response(
                "Metadata name is required", status=status.HTTP_400_BAD_REQUEST
            )

        try:
            DojoMeta.objects.update_or_create(
                name=metadata_name,
                finding=finding,
                defaults={
                    "name": request.data.get("name"),
                    "value": request.data.get("value"),
                },
            )

            return Response(data=request.data, status=status.HTTP_200_OK)
        except IntegrityError:
            return Response(
                "Update failed because the new name already exists",
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _add_metadata(self, request, finding):
        metadata_data = serializers.FindingMetaSerializer(data=request.data)

        if metadata_data.is_valid():
            name = metadata_data.validated_data["name"]
            value = metadata_data.validated_data["value"]

            metadata = DojoMeta(finding=finding, name=name, value=value)
            try:
                metadata.validate_unique()
                metadata.save()
            except ValidationError:
                return Response(
                    "Create failed probably because the name of the metadata already exists",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(data=metadata_data.data, status=status.HTTP_200_OK)
        else:
            return Response(metadata_data.errors, status=status.HTTP_400_BAD_REQUEST)

    def _remove_metadata(self, request, finding):
        name = request.query_params.get("name", None)
        if name is None:
            return Response(
                "A metadata name must be provided", status=status.HTTP_400_BAD_REQUEST
            )

        metadata = get_object_or_404(DojoMeta.objects, finding=finding, name=name)
        metadata.delete()

        return Response("Metadata deleted", status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            status.HTTP_200_OK: serializers.FindingMetaSerializer(many=True),
            status.HTTP_404_NOT_FOUND: "Returned if finding does not exist",
        },
        methods=["get"],
    )
    @swagger_auto_schema(
        responses={
            status.HTTP_200_OK: "Returned if the metadata was correctly deleted",
            status.HTTP_404_NOT_FOUND: "Returned if finding does not exist",
            status.HTTP_400_BAD_REQUEST: "Returned if there was a problem with the metadata information",
        },
        methods=["delete"],
        manual_parameters=[
            openapi.Parameter(
                name="name",
                in_=openapi.IN_QUERY,
                required=True,
                type=openapi.TYPE_STRING,
                description="name of the metadata to retrieve. If name is empty, return all the \
                            metadata associated with the finding",
            )
        ],
    )
    @swagger_auto_schema(
        responses={
            status.HTTP_200_OK: serializers.FindingMetaSerializer,
            status.HTTP_404_NOT_FOUND: "Returned if finding does not exist",
            status.HTTP_400_BAD_REQUEST: "Returned if there was a problem with the metadata information",
        },
        methods=["put"],
        manual_parameters=[
            openapi.Parameter(
                name="name",
                in_=openapi.IN_QUERY,
                required=True,
                type=openapi.TYPE_STRING,
                description="name of the metadata to edit",
            )
        ],
        request_body=serializers.FindingMetaSerializer,
    )
    @swagger_auto_schema(
        responses={
            status.HTTP_200_OK: serializers.FindingMetaSerializer,
            status.HTTP_404_NOT_FOUND: "Returned if finding does not exist",
            status.HTTP_400_BAD_REQUEST: "Returned if there was a problem with the metadata information",
        },
        methods=["post"],
        request_body=serializers.FindingMetaSerializer,
    )
    @action(detail=True, methods=["post", "put", "delete", "get"])
    def metadata(self, request, pk=None):
        finding = get_object_or_404(Finding.objects, id=pk)

        if request.method == "GET":
            return self._get_metadata(request, finding)
        elif request.method == "POST":
            return self._add_metadata(request, finding)
        elif request.method == "PUT":
            return self._edit_metadata(request, finding)
        elif request.method == "PATCH":
            return self._edit_metadata(request, finding)
        elif request.method == "DELETE":
            return self._remove_metadata(request, finding)

        return Response(
            {"error", "unsupported method"}, status=status.HTTP_400_BAD_REQUEST
        )


class JiraInstanceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.JIRAInstanceSerializer
    queryset = JIRA_Instance.objects.all()

    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "url")


class JiraIssuesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.JIRAIssueSerializer
    queryset = JIRA_Issue.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "jira_id", "jira_key", "finding_id")


class JiraProjectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.JIRAProjectSerializer
    queryset = JIRA_Project.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "id",
        "jira_instance",
        "product",
        "component",
        "project_key",
        "push_all_issues",
        "enable_engagement_epic_mapping",
        "push_notes",
    )


class SonarqubeIssueViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.SonarqubeIssueSerializer
    queryset = Sonarqube_Issue.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "key", "status", "type")


class SonarqubeIssueTransitionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.SonarqubeIssueTransitionSerializer
    queryset = Sonarqube_Issue_Transition.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "id",
        "sonarqube_issue",
        "finding_status",
        "sonarqube_status",
        "transitions",
    )


class SonarqubeProductViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.SonarqubeProductSerializer
    queryset = Sonarqube_Product.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "product", "sonarqube_project_key", "sonarqube_tool_config")


class DojoMetaViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.MetaSerializer
    queryset = DojoMeta.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "product", "endpoint", "name", "finding")


class ProductViewSet(
    prefetch.PrefetchListMixin,
    prefetch.PrefetchRetrieveMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.ProductSerializer
    # TODO: prefetch
    queryset = Product.objects.all()
    queryset = queryset.annotate(
        active_finding_count=Count(
            "engagement__test__finding__id",
            filter=Q(engagement__test__finding__active=True),
        )
    )
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.UserHasProductPermission, DjangoModelPermissions)

    filterset_class = ApiProductFilter
    swagger_schema = prefetch.get_prefetch_schema(
        ["products_list", "products_read"], serializers.ProductSerializer
    ).to_schema()

    def get_queryset(self):
        if not self.request.user.is_staff:
            return self.queryset.filter(
                Q(authorized_users__in=[self.request.user])
                | Q(prod_type__authorized_users__in=[self.request.user])
            )
        else:
            return self.queryset

    @swagger_auto_schema(
        request_body=serializers.ReportGenerateOptionSerializer,
        responses={status.HTTP_200_OK: serializers.ReportGenerateSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.UserHasReportGeneratePermission],
    )
    def generate_report(self, request, pk=None):
        product = get_object_or_404(Product.objects, id=pk)

        options = {}
        # prepare post data
        report_options = serializers.ReportGenerateOptionSerializer(data=request.data)
        if report_options.is_valid():
            options["include_finding_notes"] = report_options.validated_data[
                "include_finding_notes"
            ]
            options["include_finding_images"] = report_options.validated_data[
                "include_finding_images"
            ]
            options["include_executive_summary"] = report_options.validated_data[
                "include_executive_summary"
            ]
            options["include_table_of_contents"] = report_options.validated_data[
                "include_table_of_contents"
            ]
        else:
            return Response(report_options.errors, status=status.HTTP_400_BAD_REQUEST)

        data = report_generate(request, product, options)
        report = serializers.ReportGenerateSerializer(data)
        return Response(report.data)


class ProductTypeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.ProductTypeSerializer
    queryset = Product_Type.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "id",
        "name",
        "critical_product",
        "key_product",
        "created",
        "updated",
    )

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Product_Type.objects.filter(
                prod_type__authorized_users__in=[self.request.user]
            )
        else:
            return Product_Type.objects.all()

    @swagger_auto_schema(
        request_body=serializers.ReportGenerateOptionSerializer,
        responses={status.HTTP_200_OK: serializers.ReportGenerateSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.UserHasReportGeneratePermission],
    )
    def generate_report(self, request, pk=None):
        product_type = get_object_or_404(Product_Type.objects, id=pk)

        options = {}
        # prepare post data
        report_options = serializers.ReportGenerateOptionSerializer(data=request.data)
        if report_options.is_valid():
            options["include_finding_notes"] = report_options.validated_data[
                "include_finding_notes"
            ]
            options["include_finding_images"] = report_options.validated_data[
                "include_finding_images"
            ]
            options["include_executive_summary"] = report_options.validated_data[
                "include_executive_summary"
            ]
            options["include_table_of_contents"] = report_options.validated_data[
                "include_table_of_contents"
            ]
        else:
            return Response(report_options.errors, status=status.HTTP_400_BAD_REQUEST)

        data = report_generate(request, product_type, options)
        report = serializers.ReportGenerateSerializer(data)
        return Response(report.data)


class ScanSettingsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.ScanSettingsSerializer
    queryset = ScanSettings.objects.all()
    permission_classes = (
        permissions.UserHasScanSettingsPermission,
        DjangoModelPermissions,
    )
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "date", "user", "frequency", "product", "addresses")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return serializers.ScanSettingsCreateSerializer
        else:
            return serializers.ScanSettingsSerializer

    def get_queryset(self):
        if not self.request.user.is_staff:
            return ScanSettings.objects.filter(
                Q(product__authorized_users__in=[self.request.user])
                | Q(product__prod_type__authorized_users__in=[self.request.user])
            )
        else:
            return ScanSettings.objects.all()


class ScansViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # TODO: ipscans
    serializer_class = serializers.ScanSerializer
    queryset = Scan.objects.all()
    permission_classes = (permissions.UserHasScanPermission, DjangoModelPermissions)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "date", "scan_settings")

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Scan.objects.filter(
                Q(scan_settings__product__authorized_users__in=[self.request.user])
                | Q(
                    scan_settings__product__prod_type__authorized_users__in=[
                        self.request.user
                    ]
                )
            )
        else:
            return Scan.objects.all()


class StubFindingsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.StubFindingSerializer
    queryset = Stub_Finding.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "title", "date", "severity", "description")

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Finding.objects.filter(
                Q(test__engagement__product__authorized_users__in=[self.request.user])
                | Q(
                    test__engagement__product__prod_type__authorized_users__in=[
                        self.request.user
                    ]
                )
            )
        else:
            return Finding.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return serializers.StubFindingCreateSerializer
        else:
            return serializers.StubFindingSerializer


class DevelopmentEnvironmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.DevelopmentEnvironmentSerializer
    queryset = Development_Environment.objects.all()
    filter_backends = (DjangoFilterBackend,)


class TestsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    ra_api.AcceptedRisksMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.TestSerializer
    queryset = Test.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_class = ApiTestFilter

    @property
    def risk_application_model_class(self):
        return Test

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Test.objects.filter(
                engagement__product__authorized_users__in=[self.request.user]
            )
        else:
            return Test.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            if self.action == "accept_risks":
                return ra_api.AcceptedRiskSerializer
            return serializers.TestCreateSerializer
        else:
            return serializers.TestSerializer

    @swagger_auto_schema(
        request_body=serializers.ReportGenerateOptionSerializer,
        responses={status.HTTP_200_OK: serializers.ReportGenerateSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.UserHasReportGeneratePermission],
    )
    def generate_report(self, request, pk=None):
        test = get_object_or_404(Test.objects, id=pk)

        options = {}
        # prepare post data
        report_options = serializers.ReportGenerateOptionSerializer(data=request.data)
        if report_options.is_valid():
            options["include_finding_notes"] = report_options.validated_data[
                "include_finding_notes"
            ]
            options["include_finding_images"] = report_options.validated_data[
                "include_finding_images"
            ]
            options["include_executive_summary"] = report_options.validated_data[
                "include_executive_summary"
            ]
            options["include_table_of_contents"] = report_options.validated_data[
                "include_table_of_contents"
            ]
        else:
            return Response(report_options.errors, status=status.HTTP_400_BAD_REQUEST)

        data = report_generate(request, test, options)
        report = serializers.ReportGenerateSerializer(data)
        return Response(report.data)

    @action(detail=True, methods=["get", "post", "patch"])
    def notes(self, request, pk=None):
        test = get_object_or_404(Test.objects, id=pk)
        if request.method == "POST":
            new_note = serializers.AddNewNoteOptionSerializer(data=request.data)
            if new_note.is_valid():
                entry = new_note.validated_data["entry"]
                private = new_note.validated_data["private"]
                note_type = new_note.validated_data["note_type"]
            else:
                return Response(new_note.errors, status=status.HTTP_400_BAD_REQUEST)

            author = request.user
            note = Notes(
                entry=entry, author=author, private=private, note_type=note_type
            )
            note.save()
            test.notes.add(note)

            serialized_note = serializers.NoteSerializer(
                {"author": author, "entry": entry, "private": private}
            )
            result = serializers.TestToNotesSerializer(
                {"test_id": test, "notes": [serialized_note.data]}
            )
            return Response(serialized_note.data, status=status.HTTP_200_OK)
        notes = test.notes.all()

        serialized_notes = []
        if notes:
            serialized_notes = serializers.TestToNotesSerializer(
                {"test_id": test, "notes": notes}
            )
            return Response(serialized_notes.data, status=status.HTTP_200_OK)

        return Response(serialized_notes, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        method="get", responses={status.HTTP_200_OK: serializers.TestToFilesSerializer}
    )
    @swagger_auto_schema(
        methods=["post", "patch"],
        request_body=serializers.AddNewFileOptionSerializer,
        responses={status.HTTP_200_OK: serializers.FileSerializer},
    )
    @action(detail=True, methods=["get", "post", "patch"])
    def files(self, request, pk=None):
        test = get_object_or_404(Test.objects, id=pk)
        if request.method == "POST":
            new_file = serializers.FileSerializer(data=request.data)
            if new_file.is_valid():
                title = new_file.validated_data["title"]
                file = new_file.validated_data["file"]
            else:
                return Response(new_file.errors, status=status.HTTP_400_BAD_REQUEST)

            file = FileUpload(title=title, file=file)
            file.save()
            test.files.add(file)

            serialized_file = serializers.FileSerializer(
                {
                    "title": title,
                    "file": file,
                }
            )
            result = serializers.TestToFilesSerializer(
                {"test_id": test, "files": [serialized_file.data]}
            )
            return Response(serialized_file.data, status=status.HTTP_200_OK)
        files = test.files.all()

        serialized_files = []
        if files:
            serialized_files = serializers.TestToFilesSerializer(
                {"test_id": test, "files": files}
            )
            return Response(serialized_files.data, status=status.HTTP_200_OK)

        return Response(serialized_files, status=status.HTTP_200_OK)


class TestTypesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.TestTypeSerializer
    queryset = Test_Type.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("name",)


class ToolConfigurationsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.ToolConfigurationSerializer
    queryset = Tool_Configuration.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "name", "tool_type", "url", "authentication_type")


class ToolProductSettingsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.ToolProductSettingsSerializer
    queryset = Tool_Product_Settings.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "id",
        "name",
        "product",
        "tool_configuration",
        "tool_project_id",
        "url",
    )


class ToolTypesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.ToolTypeSerializer
    queryset = Tool_Type.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "name", "description")


class RegulationsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.RegulationSerializer
    queryset = Regulation.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "name", "description")


class UsersViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.UserSerializer
    queryset = User.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ("id", "username", "first_name", "last_name")


class ImportScanView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.ImportScanSerializer
    parser_classes = [MultiPartParser]
    queryset = Test.objects.all()

    def perform_create(self, serializer):
        engagement = serializer.validated_data["engagement"]
        jira_project = jira_helper.get_jira_project(engagement)

        push_to_jira = serializer.validated_data.get("push_to_jira")
        if get_system_setting("enable_jira") and jira_project:
            push_to_jira = push_to_jira or jira_project.push_all_issues

        logger.debug("push_to_jira: %s", serializer.validated_data.get("push_to_jira"))
        serializer.save(push_to_jira=push_to_jira)


class ReImportScanView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.ReImportScanSerializer
    parser_classes = [MultiPartParser]
    queryset = Test.objects.all()

    def perform_create(self, serializer):
        test = serializer.validated_data["test"]
        jira_project = jira_helper.get_jira_project(test)

        push_to_jira = serializer.validated_data.get("push_to_jira")
        if get_system_setting("enable_jira") and jira_project:
            push_to_jira = push_to_jira or jira_project.push_all_issues

        logger.debug("push_to_jira: %s", serializer.validated_data.get("push_to_jira"))
        serializer.save(push_to_jira=push_to_jira)


class NoteTypeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.NoteTypeSerializer
    queryset = Note_Type.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "id",
        "name",
        "description",
        "is_single",
        "is_active",
        "is_mandatory",
    )


class NotesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.NoteSerializer
    queryset = Notes.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = (
        "id",
        "entry",
        "author",
        "private",
        "date",
        "edited",
        "edit_time",
        "editor",
    )


def report_generate(request, obj, options):
    user = Dojo_User.objects.get(id=request.user.id)
    product_type = None
    product = None
    engagement = None
    test = None
    endpoint = None
    endpoints = None
    endpoint_all_findings = None
    endpoint_monthly_counts = None
    endpoint_active_findings = None
    accepted_findings = None
    open_findings = None
    closed_findings = None
    verified_findings = None
    report_title = None
    report_subtitle = None

    include_finding_notes = False
    include_finding_images = False
    include_executive_summary = False
    include_table_of_contents = False

    report_info = "Generated By %s on %s" % (
        user.get_full_name(),
        (timezone.now().strftime("%m/%d/%Y %I:%M%p %Z")),
    )

    # generate = "_generate" in request.GET
    report_name = str(obj)
    report_type = type(obj).__name__

    include_finding_notes = options.get("include_finding_notes", False)
    include_finding_images = options.get("include_finding_images", False)
    include_executive_summary = options.get("include_executive_summary", False)
    include_table_of_contents = options.get("include_table_of_contents", False)

    if type(obj).__name__ == "Product_Type":
        product_type = obj

        report_name = "Product Type Report: " + str(product_type)
        report_title = "Product Type Report"
        report_subtitle = str(product_type)

        findings = ReportFindingFilter(
            request.GET,
            prod_type=prod_type,
            queryset=prefetch_related_findings_for_report(
                Finding.objects.filter(
                    test__engagement__product__prod_type=product_type
                )
            ),
        )
        products = Product.objects.filter(
            prod_type=product_type, engagement__test__finding__in=findings.qs
        ).distinct()
        engagements = Engagement.objects.filter(
            product__prod_type=product_type, test__finding__in=findings.qs
        ).distinct()
        tests = Test.objects.filter(
            engagement__product__prod_type=product_type, finding__in=findings.qs
        ).distinct()
        if len(findings.qs) > 0:
            start_date = timezone.make_aware(
                datetime.combine(findings.qs.last().date, datetime.min.time())
            )
        else:
            start_date = timezone.now()

        end_date = timezone.now()

        r = relativedelta(end_date, start_date)
        months_between = (r.years * 12) + r.months
        # include current month
        months_between += 1

        endpoint_monthly_counts = get_period_counts_legacy(
            findings.qs.order_by("numerical_severity"),
            findings.qs.order_by("numerical_severity"),
            None,
            months_between,
            start_date,
            relative_delta="months",
        )

    elif type(obj).__name__ == "Product":
        product = obj

        report_name = "Product Report: " + str(product)
        report_title = "Product Report"
        report_subtitle = str(product)
        findings = ReportFindingFilter(
            request.GET,
            product=product,
            queryset=prefetch_related_findings_for_report(
                Finding.objects.filter(test__engagement__product=product)
            ),
        )
        ids = set(finding.id for finding in findings.qs)
        engagements = Engagement.objects.filter(test__finding__id__in=ids).distinct()
        tests = Test.objects.filter(finding__id__in=ids).distinct()
        ids = get_endpoint_ids(Endpoint.objects.filter(product=product).distinct())
        endpoints = Endpoint.objects.filter(id__in=ids)

    elif type(obj).__name__ == "Engagement":
        engagement = obj
        findings = ReportFindingFilter(
            request.GET,
            engagement=engagement,
            queryset=prefetch_related_findings_for_report(
                Finding.objects.filter(test__engagement=engagement)
            ),
        )
        report_name = "Engagement Report: " + str(engagement)

        report_title = "Engagement Report"
        report_subtitle = str(engagement)

        ids = set(finding.id for finding in findings.qs)
        tests = Test.objects.filter(finding__id__in=ids).distinct()
        ids = get_endpoint_ids(
            Endpoint.objects.filter(product=engagement.product).distinct()
        )
        endpoints = Endpoint.objects.filter(id__in=ids)

    elif type(obj).__name__ == "Test":
        test = obj
        findings = ReportFindingFilter(
            request.GET,
            engagement=test.engagement,
            queryset=prefetch_related_findings_for_report(
                Finding.objects.filter(test=test)
            ),
        )
        filename = "test_finding_report.pdf"
        template = "dojo/test_pdf_report.html"
        report_name = "Test Report: " + str(test)
        report_title = "Test Report"
        report_subtitle = str(test)

    elif type(obj).__name__ == "Endpoint":
        endpoint = obj
        host = endpoint.host_no_port
        report_name = "Endpoint Report: " + host
        report_type = "Endpoint"
        endpoints = Endpoint.objects.filter(
            host__regex="^" + host + ":?", product=endpoint.product
        ).distinct()
        report_title = "Endpoint Report"
        report_subtitle = host
        findings = ReportFindingFilter(
            request.GET,
            queryset=prefetch_related_findings_for_report(
                Finding.objects.filter(endpoints__in=endpoints)
            ),
        )

    elif type(obj).__name__ == "QuerySet":
        findings = ReportAuthedFindingFilter(
            request.GET,
            queryset=prefetch_related_findings_for_report(obj).distinct(),
            user=request.user,
        )

        report_name = "Finding"
        report_type = "Finding"
        report_title = "Finding Report"
        report_subtitle = ""

    else:
        raise Http404()

    result = {
        "product_type": product_type,
        "product": product,
        "engagement": engagement,
        "report_name": report_name,
        "report_info": report_info,
        "test": test,
        "endpoint": endpoint,
        "endpoints": endpoints,
        "findings": findings.qs.order_by("numerical_severity"),
        "include_table_of_contents": include_table_of_contents,
        "user": user,
        "team_name": settings.TEAM_NAME,
        "title": "Generate Report",
        "user_id": request.user.id,
        "host": report_url_resolver(request),
    }

    finding_notes = []
    finding_images = []

    if include_finding_images:
        for finding in findings.qs.order_by("numerical_severity"):
            images = finding.images.all()
            if images:
                finding_images.append({"finding_id": finding, "images": images})
        result["finding_images"] = finding_images

    if include_finding_notes:
        for finding in findings.qs.order_by("numerical_severity"):
            notes = finding.notes.all()
            if notes:
                finding_notes.append(
                    {
                        "finding_id": finding,
                        "notes": notes.filter(
                            private=False
                        ),  # fetching only public notes for report
                    }
                )
        result["finding_notes"] = finding_notes

    # Generating Executive summary based on obj type
    if include_executive_summary and type(obj).__name__ != "Endpoint":
        executive_summary = {}

        # Declare all required fields for executive summary
        engagement_name = None
        engagement_target_start = None
        engagement_target_end = None
        test_type_name = None
        test_target_start = None
        test_target_end = None
        test_environment_name = "unknown"  # a default of "unknown"
        test_strategy_ref = None
        total_findings = 0

        if type(obj).__name__ == "Product_Type":
            for prod_typ in obj.prod_type.all():
                engmnts = prod_typ.engagement_set.all()
                if engmnts:
                    for eng in engmnts:
                        if eng.name:
                            engagement_name = eng.name
                        engagement_target_start = eng.target_start
                        if eng.target_end:
                            engagement_target_end = eng.target_end
                        else:
                            engagement_target_end = "ongoing"
                        if eng.test_set.all():
                            for t in eng.test_set.all():
                                test_type_name = t.test_type.name
                                if test.environment:
                                    test_environment_name = t.environment.name
                                test_target_start = t.target_start
                                if t.target_end:
                                    test_target_end = t.target_end
                                else:
                                    test_target_end = "ongoing"
                            if eng.test_strategy:
                                test_strategy_ref = eng.test_strategy
                            else:
                                test_strategy_ref = ""
                total_findings = len(findings.qs.all())

        elif type(obj).__name__ == "Product":
            engs = obj.engagement_set.all()
            if engs:
                for eng in engs:
                    if eng.name:
                        engagement_name = eng.name
                    engagement_target_start = eng.target_start
                    if eng.target_end:
                        engagement_target_end = eng.target_end
                    else:
                        engagement_target_end = "ongoing"

                    if eng.test_set.all():
                        for t in eng.test_set.all():
                            test_type_name = t.test_type.name
                            if t.environment:
                                test_environment_name = t.environment.name
                    if eng.test_strategy:
                        test_strategy_ref = eng.test_strategy
                    else:
                        test_strategy_ref = ""
                total_findings = len(findings.qs.all())

        elif type(obj).__name__ == "Engagement":
            eng = obj
            if eng.name:
                engagement_name = eng.name
            engagement_target_start = eng.target_start
            if eng.target_end:
                engagement_target_end = eng.target_end
            else:
                engagement_target_end = "ongoing"

            if eng.test_set.all():
                for t in eng.test_set.all():
                    test_type_name = t.test_type.name
                    if t.environment:
                        test_environment_name = t.environment.name
            if eng.test_strategy:
                test_strategy_ref = eng.test_strategy
            else:
                test_strategy_ref = ""
            total_findings = len(findings.qs.all())

        elif type(obj).__name__ == "Test":
            t = obj
            test_type_name = t.test_type.name
            test_target_start = t.target_start
            if t.target_end:
                test_target_end = t.target_end
            else:
                test_target_end = "ongoing"
            total_findings = len(findings.qs.all())
            if t.engagement.name:
                engagement_name = t.engagement.name
            engagement_target_start = t.engagement.target_start
            if t.engagement.target_end:
                engagement_target_end = t.engagement.target_end
            else:
                engagement_target_end = "ongoing"
        else:
            pass  # do nothing

        executive_summary = {
            "engagement_name": engagement_name,
            "engagement_target_start": engagement_target_start,
            "engagement_target_end": engagement_target_end,
            "test_type_name": test_type_name,
            "test_target_start": test_target_start,
            "test_target_end": test_target_end,
            "test_environment_name": test_environment_name,
            "test_strategy_ref": test_strategy_ref,
            "total_findings": total_findings,
        }
        # End of executive summary generation

        result["executive_summary"] = executive_summary

    return result


class SystemSettingsViewSet(
    mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """ Basic control over System Settings. Use 'id' 1 for PUT, PATCH operations """

    permission_classes = (permissions.IsSuperUser, DjangoModelPermissions)
    serializer_class = serializers.SystemSettingsSerializer
    queryset = System_Settings.objects.all()
