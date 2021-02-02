import logging

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from dojo.utils import add_breadcrumb

from dojo.forms import LoginBanner
from dojo.models import BannerConf

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_superuser)
def configure_banner(request):
    banner_config = get_object_or_404(BannerConf, id=1)
    if request.method == "POST":
        form = LoginBanner(request.POST)
        if form.is_valid():
            banner_config.banner_enable = form.cleaned_data["banner_enable"]
            banner_config.banner_message = form.cleaned_data["banner_message"]
            banner_config.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Banner updated successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("configure_banner"))
    else:
        # List the banner configuration
        form = LoginBanner(
            initial={
                "banner_enable": banner_config.banner_enable,
                "banner_message": banner_config.banner_message,
            }
        )

    add_breadcrumb(title="Banner Configuration", top_level=True, request=request)
    return render(
        request,
        "dojo/banner.html",
        {"form": form, "banner_message": banner_config.banner_message},
    )
