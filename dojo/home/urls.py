from django.conf.urls import url

from dojo.home import views

urlpatterns = [
    #  dojo home pages
    url(r"^$", views.home, name="home"),
    url(r"^dashboard$", views.dashboard, name="dashboard"),
]
