# import the settings file
from django.conf import settings


def globalize_oauth_vars(request):
    # return the value you want as a dictionnary. you may add multiple values in there.
    return {
        "SHOW_LOGIN_FORM": settings.SHOW_LOGIN_FORM,
        "CLASSIC_AUTH_ENABLED": settings.CLASSIC_AUTH_ENABLED,
        "AUTH0_ENABLED": settings.AUTH0_OAUTH2_ENABLED,
        "GOOGLE_ENABLED": settings.GOOGLE_OAUTH_ENABLED,
        "OKTA_ENABLED": settings.OKTA_OAUTH_ENABLED,
        "GITLAB_ENABLED": settings.GITLAB_OAUTH2_ENABLED,
        "AZUREAD_TENANT_OAUTH2_ENABLED": settings.AZUREAD_TENANT_OAUTH2_ENABLED,
        "SAML2_ENABLED": settings.SAML2_ENABLED,
        "SAML2_LOGOUT_URL": settings.SAML2_LOGOUT_URL,
    }


def bind_system_settings(request):
    from dojo.models import System_Settings

    return {"system_settings": System_Settings.objects.get()}


def bind_alert_count(request):
    if not settings.DISABLE_ALERT_COUNTER:
        from dojo.models import Alerts

        if request.user.is_authenticated:
            return {"alert_count": Alerts.objects.filter(user_id=request.user).count()}
    return {}
