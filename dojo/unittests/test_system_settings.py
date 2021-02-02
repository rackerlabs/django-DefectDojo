from django.test import TestCase
from dojo.models import System_Settings


class TestSystemSettings(TestCase):
    def test_system_settings_update(self):
        try:
            # although the unittests are run after initial data has been loaded, for some reason in cicd sometimes the settings aren't present
            system_settings = System_Settings.objects.get()
        except System_Settings.DoesNotExist:
            system_settings = System_Settings()

        system_settings.enable_jira = True
        system_settings.save()
        system_settings = System_Settings.objects.get()
        self.assertEquals(system_settings.enable_jira, True)

        system_settings.enable_jira = False
        system_settings.save()
        system_settings = System_Settings.objects.get()
        self.assertEquals(system_settings.enable_jira, False)

        system_settings.enable_jira = True
        system_settings.save()
        system_settings = System_Settings.objects.get(no_cache=True)
        self.assertEquals(system_settings.enable_jira, True)
