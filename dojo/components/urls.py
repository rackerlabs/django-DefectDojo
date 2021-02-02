from django.conf.urls import url
from dojo.components import views

urlpatterns = [
    url(r"^components$", views.components, name="components"),
]
