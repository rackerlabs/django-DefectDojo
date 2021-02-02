# #  product
import logging
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.shortcuts import render
from dojo.models import System_Settings, enable_disable_auditlog
from dojo.utils import add_breadcrumb, get_celery_worker_status
from dojo.forms import SystemSettingsForm
from django.conf import settings
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_superuser)
def system_settings(request):
    system_settings_obj = System_Settings.objects.get(no_cache=True)

    """
    **** To be Finished JIRA Status info ****
    jira_bool = True
    jira_msg = 'None'
    if not celery_bool:
        jira_bool = False
        jira_msg = 'Celery is not working properly'
    else:

        try:
            jira_server = jform.cleaned_data.get('url').rstrip('/')
            jira = JIRA(server=jform.cleaned_data.get('url').rstrip('/'),
                        basic_auth=(jform.cleaned_data.get('username'), jform.cleaned_data.get('password')))
            new_j = jform.save(commit=False)
            new_j.url = jira_server
            new_j.save()
            messages.add_message(request,
                                 messages.SUCCESS,

                                 'JIRA Configuration Successfully Created.',
                                 extra_tags='alert-success')
            return HttpResponseRedirect(reverse('jira', ))
        except:
            messages.add_message(request,
                                 messages.ERROR,
                                 'Unable to authenticate to JIRA. Please check the URL, username, and password.',
                                 extra_tags='alert-danger')

    """
    form = SystemSettingsForm(instance=system_settings_obj)
    if request.method == "POST":
        form = SystemSettingsForm(request.POST, instance=system_settings_obj)
        if form.is_valid():
            new_settings = form.save()
            enable_disable_auditlog(enable=new_settings.enable_auditlog)
            messages.add_message(
                request, messages.SUCCESS, "Settings saved.", extra_tags="alert-success"
            )
            return HttpResponseRedirect(
                reverse(
                    "system_settings",
                )
            )
    else:
        # Celery needs to be set with the setting: CELERY_RESULT_BACKEND = 'db+sqlite:///dojo.celeryresults.sqlite'
        if hasattr(settings, "CELERY_RESULT_BACKEND"):
            # Check the status of Celery by sending calling a celery task
            celery_bool = get_celery_worker_status()

            if celery_bool:
                celery_msg = "Celery is processing tasks."
                celery_status = "Running"
            else:
                celery_msg = "Celery does not appear to be up and running. Please ensure celery is running."
                celery_status = "Not Running"
        else:
            celery_bool = False
            celery_msg = "Celery needs to have the setting CELERY_RESULT_BACKEND = 'db+sqlite:///dojo.celeryresults.sqlite' set in settings.py."
            celery_status = "Unkown"

    add_breadcrumb(title="Application settings", top_level=False, request=request)
    return render(
        request,
        "dojo/system_settings.html",
        {
            "form": form,
            "celery_bool": celery_bool,
            "celery_msg": celery_msg,
            "celery_status": celery_status,
        },
    )
