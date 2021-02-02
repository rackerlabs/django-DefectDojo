from django.conf.urls import url

from dojo.search import views

urlpatterns = [
    #  search
    url(r"^simple_search$", views.simple_search, name="simple_search"),
]
