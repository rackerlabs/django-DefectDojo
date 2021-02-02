from django.conf.urls import url, include
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm

from dojo.user import views

urlpatterns = [
    # social-auth-django required url package
    url("", include("social_django.urls", namespace="social")),
    #  user specific
    url(
        r"^login$",
        LoginView.as_view(
            template_name="dojo/login.html", authentication_form=AuthenticationForm
        ),
        name="login",
    ),
    url(r"^logout$", views.logout_view, name="logout"),
    url(r"^alerts$", views.alerts, name="alerts"),
    url(r"^alerts/json$", views.alerts_json, name="alerts_json"),
    url(r"^alerts/count$", views.alertcount, name="alertcount"),
    url(r"^delete_alerts$", views.delete_alerts, name="delete_alerts"),
    url(r"^profile$", views.view_profile, name="view_profile"),
    url(r"^change_password$", views.change_password, name="change_password"),
    url(r"^user$", views.user, name="users"),
    url(r"^user/add$", views.add_user, name="add_user"),
    url(r"^user/(?P<uid>\d+)/edit$", views.edit_user, name="edit_user"),
    url(r"^user/(?P<uid>\d+)/delete", views.delete_user, name="delete_user"),
    url(r"^api/key$", views.api_key, name="api_key"),
    url(r"^api/key-v2$", views.api_v2_key, name="api_v2_key"),
]
