from django.conf.urls import url

from dojo.scan import views

urlpatterns = [
    # scans and scan settings
    url(r"^scan/(?P<sid>\d+)$", views.view_scan, name="view_scan"),
    url(r"^product/(?P<pid>\d+)/scan/add$", views.gmap, name="gmap"),
    url(
        r"^product/(?P<pid>\d+)/scan/(?P<sid>\d+)/settings$",
        views.view_scan_settings,
        name="view_scan_settings",
    ),
    url(
        r"^product/(?P<pid>\d+)/scan/(?P<sid>\d+)/edit$",
        views.edit_scan_settings,
        name="edit_scan_settings",
    ),
    # other
    url(r"^launch_va/(?P<pid>\d+)$", views.launch_va, name="launch_va"),
]
