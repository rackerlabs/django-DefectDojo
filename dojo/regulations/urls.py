from django.conf.urls import url
from . import views

urlpatterns = [
    url(r"^regulations/add", views.new_regulation, name="new_regulation"),
    url(
        r"^regulations/(?P<ttid>\d+)/edit$",
        views.edit_regulations,
        name="edit_regulations",
    ),
    url(r"^regulations$", views.regulations, name="regulations"),
]
