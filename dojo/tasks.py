import logging
import tempfile
import pdfkit
from datetime import timedelta
from django.db.models import Count, Prefetch
from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.http import urlencode
from dojo.celery import app
from celery.utils.log import get_task_logger
from celery.decorators import task
from dojo.models import Alerts, Product, Finding, Engagement, System_Settings, User
from django.utils import timezone
from dojo.utils import calculate_grade
from dojo.reports.widgets import report_widget_factory
from dojo.utils import sla_compute_and_notify
from dojo.notifications.helper import create_notification


logger = get_task_logger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


# Logs the error to the alerts table, which appears in the notification toolbar
def log_generic_alert(source, title, description):
    create_notification(
        event="other",
        title=title,
        description=description,
        icon="bullseye",
        source=source,
    )


@app.task(bind=True)
def add_alerts(self, runinterval):
    now = timezone.now()

    upcoming_engagements = Engagement.objects.filter(
        target_start__gt=now + timedelta(days=3),
        target_start__lt=now + timedelta(days=3) + runinterval,
    ).order_by("target_start")
    for engagement in upcoming_engagements:
        create_notification(
            event="upcoming_engagement",
            title="Upcoming engagement: %s" % engagement.name,
            engagement=engagement,
            recipients=[engagement.lead],
            url=reverse("view_engagement", args=(engagement.id,)),
        )

    stale_engagements = Engagement.objects.filter(
        target_start__gt=now - runinterval, target_end__lt=now, status="In Progress"
    ).order_by("-target_end")
    for eng in stale_engagements:
        create_notification(
            event="stale_engagement",
            title="Stale Engagement: %s" % eng.name,
            description='The engagement "%s" is stale. Target end was %s.'
            % (eng.name, eng.target_end.strftime("%b. %d, %Y")),
            url=reverse("view_engagement", args=(eng.id,)),
            recipients=[eng.lead],
        )

    system_settings = System_Settings.objects.get()
    if system_settings.engagement_auto_close:
        # Close Engagements older than user defined days
        close_days = system_settings.engagement_auto_close_days
        unclosed_engagements = Engagement.objects.filter(
            target_end__lte=now - timedelta(days=close_days), status="In Progress"
        ).order_by("target_end")

        for eng in unclosed_engagements:
            create_notification(
                event="auto_close_engagement",
                title=eng.name,
                description='The engagement "%s" has auto-closed. Target end was %s.'
                % (eng.name, eng.target_end.strftime("%b. %d, %Y")),
                url=reverse("view_engagement", args=(eng.id,)),
                recipients=[eng.lead],
            )

        unclosed_engagements.update(
            status="Completed", active=False, updated=timezone.now()
        )

    # Calculate grade
    if system_settings.enable_product_grade:
        products = Product.objects.all()
        for product in products:
            calculate_grade(product)


@app.task(bind=True)
def cleanup_alerts(*args, **kwargs):
    try:
        max_alerts_per_user = settings.MAX_ALERTS_PER_USER
    except System_Settings.DoesNotExist:
        max_alerts_per_user = -1

    if max_alerts_per_user > -1:
        total_deleted_count = 0
        logger.info(
            "start deleting oldest alerts if a user has more than %s alerts",
            max_alerts_per_user,
        )
        users = User.objects.all()
        for user in users:
            alerts_to_delete = (
                Alerts.objects.filter(user_id=user.id)
                .order_by("-created")[max_alerts_per_user:]
                .values_list("id", flat=True)
            )
            total_deleted_count += len(alerts_to_delete)
            Alerts.objects.filter(pk__in=list(alerts_to_delete)).delete()
        logger.info("total number of alerts deleted: %s", total_deleted_count)


@app.task(bind=True)
def async_pdf_report(
    self,
    report=None,
    template="None",
    filename="report.pdf",
    report_title=None,
    report_subtitle=None,
    report_info=None,
    context={},
    uri=None,
):
    xsl_style_sheet = settings.DOJO_ROOT + "/static/dojo/xsl/pdf_toc.xsl"
    x = urlencode(
        {"title": report_title, "subtitle": report_subtitle, "info": report_info}
    )

    cover = context["host"] + reverse("report_cover_page") + "?" + x

    try:
        config = pdfkit.configuration(wkhtmltopdf=settings.WKHTMLTOPDF_PATH)
        report.task_id = async_pdf_report.request.id
        report.save()
        bytes = render_to_string(template, context)
        itoc = context["include_table_of_contents"]
        if itoc:
            toc = {"xsl-style-sheet": xsl_style_sheet}
        else:
            toc = None
        pdf = pdfkit.from_string(
            bytes, False, configuration=config, cover=cover, toc=toc
        )
        if report.file.name:
            with open(report.file.path, "w") as f:
                f.write(pdf)
            f.close()
        else:
            f = ContentFile(pdf)
            report.file.save(filename, f)
        report.status = "success"
        report.done_datetime = timezone.now()
        report.save()

        create_notification(
            event="report_created",
            title="Report created",
            description='The report "%s" is ready.' % report.name,
            url=uri,
            report=report,
            objowner=report.requester,
        )
    except Exception as e:
        report.status = "error"
        report.save()
        log_generic_alert(
            "PDF Report",
            "Report Creation Failure",
            "Make sure WKHTMLTOPDF is installed. " + str(e),
        )
    return True


@app.task(bind=True)
def async_custom_pdf_report(
    self,
    report=None,
    template="None",
    filename="report.pdf",
    host=None,
    user=None,
    uri=None,
    finding_notes=False,
    finding_images=False,
):
    config = pdfkit.configuration(wkhtmltopdf=settings.WKHTMLTOPDF_PATH)

    selected_widgets = report_widget_factory(
        json_data=report.options,
        request=None,
        user=user,
        finding_notes=finding_notes,
        finding_images=finding_images,
        host=host,
    )

    widgets = list(selected_widgets.values())
    temp = None

    try:
        report.task_id = async_custom_pdf_report.request.id
        report.save()

        toc = None
        toc_depth = 4

        if "table-of-contents" in selected_widgets:
            xsl_style_sheet_tempalte = "dojo/pdf_toc.xsl"
            temp = tempfile.NamedTemporaryFile()

            toc_settings = selected_widgets["table-of-contents"]

            toc_depth = toc_settings.depth
            toc_bytes = render_to_string(
                xsl_style_sheet_tempalte,
                {"widgets": widgets, "depth": toc_depth, "title": toc_settings.title},
            )
            temp.write(toc_bytes)
            temp.seek(0)

            toc = {"toc-header-text": toc_settings.title, "xsl-style-sheet": temp.name}

        # default the cover to not come first by default
        cover_first_val = False

        cover = None
        if "cover-page" in selected_widgets:
            cover_first_val = True
            cp = selected_widgets["cover-page"]
            x = urlencode(
                {"title": cp.title, "subtitle": cp.sub_heading, "info": cp.meta_info}
            )
            cover = host + reverse("report_cover_page") + "?" + x
        bytes = render_to_string(
            template,
            {
                "widgets": widgets,
                "toc_depth": toc_depth,
                "host": host,
                "report_name": report.name,
            },
        )
        pdf = pdfkit.from_string(
            bytes,
            False,
            configuration=config,
            toc=toc,
            cover=cover,
            cover_first=cover_first_val,
        )

        if report.file.name:
            with open(report.file.path, "w") as f:
                f.write(pdf)
            f.close()
        else:
            f = ContentFile(pdf)
            report.file.save(filename, f)
        report.status = "success"
        report.done_datetime = timezone.now()
        report.save()

        create_notification(
            event="report_created",
            title="Report created",
            description='The report "%s" is ready.' % report.name,
            url=uri,
            report=report,
            objowner=report.requester,
        )
    except Exception as e:
        report.status = "error"
        report.save()
        # email_requester(report, uri, error=e)
        # raise e
        log_generic_alert(
            "PDF Report",
            "Report Creation Failure",
            "Make sure WKHTMLTOPDF is installed. " + str(e),
        )
    finally:
        if temp is not None:
            # deleting temp xsl file
            temp.close()

    return True


@app.task(bind=True)
def async_dupe_delete(*args, **kwargs):
    try:
        system_settings = System_Settings.objects.get()
        enabled = system_settings.delete_dupulicates
        dupe_max = system_settings.max_dupes
        total_duplicate_delete_count_max_per_run = settings.DUPE_DELETE_MAX_PER_RUN
    except System_Settings.DoesNotExist:
        enabled = False

    if enabled and dupe_max is None:
        logger.info("skipping deletion of excess duplicates: max_dupes not configured")
        return

    if enabled:
        logger.info(
            "delete excess duplicates (max_dupes per finding: %s, max deletes per run: %s)",
            dupe_max,
            total_duplicate_delete_count_max_per_run,
        )
        deduplicationLogger.info(
            "delete excess duplicates (max_dupes per finding: %s, max deletes per run: %s)",
            dupe_max,
            total_duplicate_delete_count_max_per_run,
        )

        # limit to 100 to prevent overlapping jobs
        results = (
            Finding.objects.filter(duplicate=True)
            .order_by()
            .values("duplicate_finding")
            .annotate(num_dupes=Count("id"))
            .filter(num_dupes__gt=dupe_max)[:total_duplicate_delete_count_max_per_run]
        )

        originals_with_too_many_duplicates_ids = [
            result["duplicate_finding"] for result in results
        ]

        originals_with_too_many_duplicates = Finding.objects.filter(
            id__in=originals_with_too_many_duplicates_ids
        ).order_by("id")

        # prefetch to make it faster
        originals_with_too_many_duplicates = (
            originals_with_too_many_duplicates.prefetch_related(
                (
                    Prefetch(
                        "original_finding",
                        queryset=Finding.objects.filter(duplicate=True).order_by(
                            "date"
                        ),
                    )
                )
            )
        )

        total_deleted_count = 0
        for original in originals_with_too_many_duplicates:
            duplicate_list = original.original_finding.all()
            dupe_count = len(duplicate_list) - dupe_max

            for finding in duplicate_list:
                deduplicationLogger.debug(
                    "deleting finding {}:{} ({}))".format(
                        finding.id, finding.title, finding.hash_code
                    )
                )
                finding.delete()
                total_deleted_count += 1
                dupe_count -= 1
                if dupe_count <= 0:
                    break
                if total_deleted_count >= total_duplicate_delete_count_max_per_run:
                    break

            if total_deleted_count >= total_duplicate_delete_count_max_per_run:
                break

        logger.info(
            "total number of excess duplicates deleted: %s", total_deleted_count
        )


@task(name="celery_status", ignore_result=False)
def celery_status():
    return True


@app.task(name="dojo.tasks.async_sla_compute_and_notify")
def async_sla_compute_and_notify_task(*args, **kwargs):
    logger.debug("Computing SLAs and notifying as needed")
    try:
        system_settings = System_Settings.objects.get()
        if system_settings.enable_finding_sla:
            sla_compute_and_notify(*args, **kwargs)
    except Exception as e:
        logger.error(
            "An unexpected error was thrown calling the SLA code: {}".format(e)
        )
