from django import template
from dojo.models import BannerConf

register = template.Library()


@register.filter
def get_banner(banner_conf):
    try:
        banner_config = BannerConf.objects.get()
        if getattr(banner_config, banner_conf, None):
            return getattr(banner_config, banner_conf, None)
        else:
            return False
    except Exception:
        return False
