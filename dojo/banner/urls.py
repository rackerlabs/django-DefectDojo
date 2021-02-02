from django.conf.urls import url
from dojo.banner import views

urlpatterns = [
    url(r"^configure_banner$", views.configure_banner, name="configure_banner"),
]
