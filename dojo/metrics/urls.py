from django.conf.urls import url

from dojo.metrics import views

urlpatterns = [
    #  metrics
    url(r"^metrics$", views.metrics, {"mtype": "All"}, name="metrics"),
    url(
        r"^critical_product_metrics$",
        views.critical_product_metrics,
        {"mtype": "All"},
        name="critical_product_metrics",
    ),
    url(r"^metrics/all$", views.metrics, {"mtype": "All"}, name="metrics_all"),
    url(
        r"^metrics/product/type$",
        views.metrics,
        {"mtype": "All"},
        name="metrics_product_type",
    ),
    url(r"^metrics/simple$", views.simple_metrics, name="simple_metrics"),
    url(
        r"^metrics/product/type/(?P<mtype>\d+)$",
        views.metrics,
        name="product_type_metrics",
    ),
    url(
        r"^metrics/product/type/counts$",
        views.product_type_counts,
        name="product_type_counts",
    ),
    url(r"^metrics/engineer$", views.engineer_metrics, name="engineer_metrics"),
    url(r"^metrics/research$", views.research_metrics, name="research_metrics"),
    url(r"^metrics/engineer/(?P<eid>\d+)$", views.view_engineer, name="view_engineer"),
]
