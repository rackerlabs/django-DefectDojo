from django.conf.urls import url

from dojo.common_note import views

urlpatterns = [
    url(r'^common_note',
        views.common_note, name='common_note'),
    url(r'^add_common_note',
        views.add_common_note, name='add_common_note'),
    url(r'^common/note/(?P<cnid>\d+)/note1$',
        views.add_common_note_comment, name='add_common_note_comment'),
    url(r'^common/note/(?P<cnid>\d+)/edit$',
        views.edit_common_note, name='edit_common_note'),
    url(r'^common/note/(?P<cnid>\d+)/view1$',
        views.view_common_note, name='view_common_note'),
]
