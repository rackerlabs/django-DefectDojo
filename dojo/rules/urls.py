from django.conf.urls import url
from dojo.rules import views

urlpatterns = [
    url(r"^rules", views.rules, name="rules"),
    url(r"^rule/add", views.new_rule, name="Add Rule"),
    url(r"^rule/(?P<pid>\d+)/edit$", views.edit_rule, name="Edit Rule"),
    url(r"^rule/(?P<pid>\d+)/add_child", views.add_child, name="Add Child"),
    url(r"^rule/(?P<tid>\d+)/delete$", views.delete_rule, name="Delete Rule"),
]
