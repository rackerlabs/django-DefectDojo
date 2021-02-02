from django.conf.urls import url

from dojo.reports import views

urlpatterns = [
    #  reports
    url(r"^reports$", views.reports, name="reports"),
    url(
        r"^product/type/(?P<ptid>\d+)/report$",
        views.product_type_report,
        name="product_type_report",
    ),
    url(r"^product/(?P<pid>\d+)/report$", views.product_report, name="product_report"),
    url(
        r"^product/(?P<pid>\d+)/endpoint/report$",
        views.product_endpoint_report,
        name="product_endpoint_report",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/report$",
        views.engagement_report,
        name="engagement_report",
    ),
    url(r"^test/(?P<tid>\d+)/report$", views.test_report, name="test_report"),
    url(
        r"^endpoint/(?P<eid>\d+)/report$", views.endpoint_report, name="endpoint_report"
    ),
    url(
        r"^product/report$",
        views.product_findings_report,
        name="product_findings_report",
    ),
    url(
        r"^reports/(?P<rid>\d+)/download$",
        views.download_report,
        name="download_report",
    ),
    url(r"^reports/(?P<rid>\d+)/delete", views.delete_report, name="delete_report"),
    url(r"^reports/(?P<rid>\d+)/status", views.report_status, name="report_status"),
    url(r"^reports/(?P<rid>\d+)/regen", views.regen_report, name="regen_report"),
    url(r"^reports/(?P<rid>\d+)/revoke", views.revoke_report, name="revoke_report"),
    url(r"^reports/cover$", views.report_cover_page, name="report_cover_page"),
    url(r"^reports/builder$", views.report_builder, name="report_builder"),
    url(r"^reports/findings$", views.report_findings, name="report_findings"),
    url(r"^reports/endpoints$", views.report_endpoints, name="report_endpoints"),
    url(r"^reports/custom$", views.custom_report, name="custom_report"),
]
