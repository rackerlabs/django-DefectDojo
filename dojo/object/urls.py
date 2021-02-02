from django.conf.urls import url
from django.contrib import admin
from django.apps import apps
from . import views

urlpatterns = [
    url(
        r"^engagement/(?P<id>\d+)/object/view$",
        views.view_object_eng,
        name="view_object_eng",
    ),
    url(r"^product/(?P<pid>\d+)/object/add$", views.new_object, name="new_object"),
    url(
        r"^product/(?P<pid>\d+)/object/(?P<ttid>\d+)/edit$",
        views.edit_object,
        name="edit_object",
    ),
    url(r"^product/(?P<pid>\d+)/object/view$", views.view_objects, name="view_objects"),
    url(
        r"^product/(?P<pid>\d+)/object/(?P<ttid>\d+)/delete$",
        views.delete_object,
        name="delete_object",
    ),
]
