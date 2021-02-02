# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app  # noqa

default_app_config = "dojo.apps.DojoAppConfig"

__version__ = "1.13.0-dev"
__url__ = "https://github.com/DefectDojo/django-DefectDojo"
__docs__ = "http://defectdojo.readthedocs.io/"
