from django.conf.urls import url

from dojo.engagement import views

urlpatterns = [
    #  engagements and calendar
    url(r"^calendar$", views.engagement_calendar, name="calendar"),
    url(
        r"^calendar/engagements$", views.engagement_calendar, name="engagement_calendar"
    ),
    url(r"^engagement$", views.engagement, name="engagement"),
    url(r"^engagements_all$", views.engagements_all, name="engagements_all"),
    url(r"^engagement/(?P<eid>\d+)$", views.view_engagement, name="view_engagement"),
    url(r"^engagement/(?P<eid>\d+)/ics$", views.engagement_ics, name="engagement_ics"),
    url(
        r"^engagement/(?P<eid>\d+)/edit$", views.edit_engagement, name="edit_engagement"
    ),
    url(
        r"^engagement/(?P<eid>\d+)/delete$",
        views.delete_engagement,
        name="delete_engagement",
    ),
    url(r"^engagement/(?P<eid>\d+)/add_tests$", views.add_tests, name="add_tests"),
    url(
        r"^engagement/(?P<eid>\d+)/import_scan_results$",
        views.import_scan_results,
        name="import_scan_results",
    ),
    url(r"^engagement/(?P<eid>\d+)/close$", views.close_eng, name="close_engagement"),
    url(
        r"^engagement/(?P<eid>\d+)/reopen$", views.reopen_eng, name="reopen_engagement"
    ),
    url(
        r"^engagement/(?P<eid>\d+)/complete_checklist$",
        views.complete_checklist,
        name="complete_checklist",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/add$",
        views.add_risk_acceptance,
        name="add_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/add/(?P<fid>\d+)$",
        views.add_risk_acceptance,
        name="add_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/(?P<raid>\d+)$",
        views.view_risk_acceptance,
        name="view_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/(?P<raid>\d+)/edit$",
        views.edit_risk_acceptance,
        name="edit_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/(?P<raid>\d+)/expire$",
        views.expire_risk_acceptance,
        name="expire_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/(?P<raid>\d+)/reinstate$",
        views.reinstate_risk_acceptance,
        name="reinstate_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/(?P<raid>\d+)/delete$",
        views.delete_risk_acceptance,
        name="delete_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/risk_acceptance/(?P<raid>\d+)/download$",
        views.download_risk_acceptance,
        name="download_risk_acceptance",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/threatmodel$",
        views.view_threatmodel,
        name="view_threatmodel",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/threatmodel/upload$",
        views.upload_threatmodel,
        name="upload_threatmodel",
    ),
]
