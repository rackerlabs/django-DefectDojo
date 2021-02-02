from django.conf.urls import url
from django.contrib import admin
from django.apps import apps
from . import views

urlpatterns = [
    url(r"^cred/add", views.new_cred, name="add_cred"),
    url(
        r"^cred/(?P<ttid>\d+)/view$", views.view_cred_details, name="view_cred_details"
    ),
    url(r"^cred/(?P<ttid>\d+)/edit$", views.edit_cred, name="edit_cred"),
    url(r"^cred/(?P<ttid>\d+)/delete$", views.delete_cred, name="delete_cred"),
    url(r"^cred/(?P<ttid>\d+)/selenium$", views.view_selenium, name="view_selenium"),
    url(r"^cred$", views.cred, name="cred"),
    url(
        r"^product/(?P<pid>\d+)/cred/add$",
        views.new_cred_product,
        name="new_cred_product",
    ),
    url(
        r"^product/(?P<pid>\d+)/cred/all$",
        views.all_cred_product,
        name="all_cred_product",
    ),
    url(
        r"^product/(?P<pid>\d+)/cred/(?P<ttid>\d+)/edit$",
        views.edit_cred_product,
        name="edit_cred_product",
    ),
    url(
        r"^product/(?P<pid>\d+)/cred/(?P<ttid>\d+)/view$",
        views.view_cred_product,
        name="view_cred_product",
    ),
    url(
        r"^product/(?P<pid>\d+)/cred/(?P<ttid>\d+)/delete$",
        views.delete_cred_product,
        name="delete_cred_product",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/cred/add$",
        views.new_cred_product_engagement,
        name="new_cred_product_engagement",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/cred/(?P<ttid>\d+)/view$",
        views.view_cred_product_engagement,
        name="view_cred_product_engagement",
    ),
    url(
        r"^engagement/(?P<eid>\d+)/cred/(?P<ttid>\d+)/delete$",
        views.delete_cred_engagement,
        name="delete_cred_engagement",
    ),
    url(
        r"^test/(?P<tid>\d+)/cred/add$",
        views.new_cred_engagement_test,
        name="new_cred_engagement_test",
    ),
    url(
        r"^test/(?P<tid>\d+)/cred/(?P<ttid>\d+)/view$",
        views.view_cred_engagement_test,
        name="view_cred_engagement_test",
    ),
    url(
        r"^test/(?P<tid>\d+)/cred/(?P<ttid>\d+)/delete$",
        views.delete_cred_test,
        name="delete_cred_test",
    ),
    url(
        r"^finding/(?P<fid>\d+)/cred/add$",
        views.new_cred_finding,
        name="new_cred_finding",
    ),
    url(
        r"^finding/(?P<fid>\d+)/cred/(?P<ttid>\d+)/view$",
        views.view_cred_finding,
        name="view_cred_finding",
    ),
    url(
        r"^finding/(?P<fid>\d+)/cred/(?P<ttid>\d+)/delete$",
        views.delete_cred_finding,
        name="delete_cred_finding",
    ),
]
