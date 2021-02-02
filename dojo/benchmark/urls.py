from django.conf.urls import url
from django.contrib import admin
from django.apps import apps
from . import views

urlpatterns = [
    url(
        r"^benchmark/(?P<pid>\d+)/type/(?P<type>\d+)$",
        views.benchmark_view,
        name="view_product_benchmark",
    ),
    url(
        r"^benchmark/(?P<pid>\d+)/type/(?P<type>\d+)/category/(?P<cat>\d+)",
        views.benchmark_view,
        name="view_product_benchmark",
    ),
    url(
        r"^benchmark/(?P<pid>\d+)/type/(?P<type>\d+)/category/(?P<cat>\d+)/edit/(?P<bid>\d+)",
        views.benchmark_view,
        name="edit_benchmark",
    ),
    url(
        r"^benchmark/(?P<pid>\d+)/type/(?P<type>\d+)/delete",
        views.delete,
        name="delete_product_benchmark",
    ),
]
