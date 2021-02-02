from django.core.management import call_command
from django.test import TestCase


class TestSampleData(TestCase):
    def test_loaddata(self):
        try:
            call_command(
                "loaddata", "dojo/fixtures/defect_dojo_sample_data", verbosity=0
            )
        except Exception as e:
            self.assertEqual(False, True, e)
        self.assertEqual(True, True)
