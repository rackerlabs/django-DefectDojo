from django.conf.urls import url

from dojo.product import views

urlpatterns = [
    #  product
    url(r"^product$", views.product, name="product"),
    url(r"^product/(?P<pid>\d+)$", views.view_product, name="view_product"),
    url(
        r"^product/(?P<pid>\d+)/components$",
        views.view_product_components,
        name="view_product_components",
    ),
    url(
        r"^product/(?P<pid>\d+)/engagements$",
        views.view_engagements,
        name="view_engagements",
    ),
    url(
        r"^product/(?P<pid>\d+)/engagements/cicd$",
        views.view_engagements_cicd,
        name="view_engagements_cicd",
    ),
    url(
        r"^product/(?P<pid>\d+)/import_scan_results$",
        views.import_scan_results_prod,
        name="import_scan_results_prod",
    ),
    url(
        r"^product/(?P<pid>\d+)/metrics$",
        views.view_product_metrics,
        name="view_product_metrics",
    ),
    url(r"^product/(?P<pid>\d+)/edit$", views.edit_product, name="edit_product"),
    url(r"^product/(?P<pid>\d+)/delete$", views.delete_product, name="delete_product"),
    url(r"^product/add", views.new_product, name="new_product"),
    url(
        r"^product/(?P<pid>\d+)/new_engagement$",
        views.new_eng_for_app,
        name="new_eng_for_prod",
    ),
    url(
        r"^product/(?P<pid>\d+)/new_technology$",
        views.new_tech_for_prod,
        name="new_tech_for_prod",
    ),
    url(
        r"^product/(?P<pid>\d+)/new_engagement/cicd$",
        views.new_eng_for_app_cicd,
        name="new_eng_for_prod_cicd",
    ),
    url(
        r"^product/(?P<pid>\d+)/add_meta_data",
        views.add_meta_data,
        name="add_meta_data",
    ),
    url(
        r"^product/(?P<pid>\d+)/edit_notifications",
        views.edit_notifications,
        name="edit_notifications",
    ),
    url(
        r"^product/(?P<pid>\d+)/edit_meta_data",
        views.edit_meta_data,
        name="edit_meta_data",
    ),
    url(
        r"^product/(?P<pid>\d+)/ad_hoc_finding",
        views.ad_hoc_finding,
        name="ad_hoc_finding",
    ),
    url(
        r"^product/(?P<pid>\d+)/engagement_presets$",
        views.engagement_presets,
        name="engagement_presets",
    ),
    url(
        r"^product/(?P<pid>\d+)/engagement_presets/(?P<eid>\d+)/edit",
        views.edit_engagement_presets,
        name="edit_engagement_presets",
    ),
    url(
        r"^product/(?P<pid>\d+)/engagement_presets/add",
        views.add_engagement_presets,
        name="add_engagement_presets",
    ),
    url(
        r"^product/(?P<pid>\d+)/engagement_presets/(?P<eid>\d+)/delete",
        views.delete_engagement_presets,
        name="delete_engagement_presets",
    ),
]
