from django.conf.urls import url

from dojo.google_sheet import views

urlpatterns = [
    #  google_sheet
    url(
        r"^configure_google_sheets$",
        views.configure_google_sheets,
        name="configure_google_sheets",
    ),
    url(
        r"^export_to_sheet/(?P<tid>\d+)$", views.export_to_sheet, name="export_to_sheet"
    ),
]
