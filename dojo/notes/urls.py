from django.conf.urls import url
from . import views

urlpatterns = [
    url(
        r"^notes/(?P<id>\d+)/delete/(?P<page>[\w-]+)/(?P<objid>\d+)$",
        views.delete_issue,
        name="delete_note",
    ),
    url(
        r"^notes/(?P<id>\d+)/edit/(?P<page>[\w-]+)/(?P<objid>\d+)$",
        views.edit_issue,
        name="edit_note",
    ),
    url(
        r"^notes/(?P<id>\d+)/history/(?P<page>[\w-]+)/(?P<objid>\d+)$",
        views.note_history,
        name="note_history",
    ),
]
