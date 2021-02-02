from django.conf.urls import url

from dojo.development_environment import views

urlpatterns = [
    # dev envs
    url(r"^dev_env$", views.dev_env, name="dev_env"),
    url(r"^dev_env/add$", views.add_dev_env, name="add_dev_env"),
    url(r"^dev_env/(?P<deid>\d+)/edit$", views.edit_dev_env, name="edit_dev_env"),
]
