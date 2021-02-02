from django.test import TestCase
from dojo.models import Test
from dojo.tools.hadolint.parser import HadolintParser


class TesthadolintParser(TestCase):
    def test_parse_file_with_one_dockerfile(self):
        testfile = open("dojo/unittests/scans/hadolint/one_dockerfile.json")
        parser = HadolintParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(4, len(findings))

    def test_parse_file_with_many_dockerfile(self):
        testfile = open("dojo/unittests/scans/hadolint/many_dockerfile.json")
        parser = HadolintParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(12, len(findings))
