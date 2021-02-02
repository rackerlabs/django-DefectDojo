# #  product
import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render

from dojo.models import Notifications
from dojo.utils import add_breadcrumb
from dojo.forms import NotificationsForm

logger = logging.getLogger(__name__)


def personal_notifications(request):
    try:
        notifications_obj = Notifications.objects.get(
            user=request.user, product__isnull=True
        )
    except:
        notifications_obj = Notifications(user=request.user)

    form = NotificationsForm(instance=notifications_obj)
    if request.method == "POST":
        form = NotificationsForm(request.POST, instance=notifications_obj)
        if form.is_valid():
            new_settings = form.save()
            messages.add_message(
                request, messages.SUCCESS, "Settings saved.", extra_tags="alert-success"
            )

    add_breadcrumb(
        title="Personal notification settings", top_level=False, request=request
    )

    return render(
        request,
        "dojo/notifications.html",
        {"form": form, "scope": "personal", "admin": request.user.is_superuser},
    )


@user_passes_test(lambda u: u.is_superuser)
def system_notifications(request):
    try:
        notifications_obj = Notifications.objects.get(user=None, product__isnull=True)
    except:
        notifications_obj = Notifications(user=None)

    form = NotificationsForm(instance=notifications_obj)
    if request.method == "POST":
        form = NotificationsForm(request.POST, instance=notifications_obj)
        if form.is_valid():
            new_settings = form.save()
            messages.add_message(
                request, messages.SUCCESS, "Settings saved.", extra_tags="alert-success"
            )

    add_breadcrumb(
        title="System notification settings", top_level=False, request=request
    )
    return render(
        request,
        "dojo/notifications.html",
        {"form": form, "scope": "system", "admin": request.user.is_superuser},
    )
