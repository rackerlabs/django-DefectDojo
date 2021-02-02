import re
from django import template
from django.conf import settings

register = template.Library()


@register.filter
def get_config_setting(config_setting):
    if hasattr(settings, config_setting):
        if getattr(settings, config_setting, None):
            return True
        else:
            return False
    else:
        return False
