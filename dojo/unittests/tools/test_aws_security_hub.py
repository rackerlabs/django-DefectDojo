import os.path

from django.test import TestCase
from dojo.tools.awssecurityhub.parser import AwsSecurityFindingFormatParser
from dojo.models import Test


def sample_path(file_name):
    return os.path.join("dojo/unittests/scans/awssecurityhub", file_name)


class TestAwsSecurityFindingFormatParser(TestCase):
    def test_one_finding(self):
        with open(sample_path("one_finding.json")) as test_file:
            parser = AwsSecurityFindingFormatParser()
            findings = parser.get_findings(test_file, Test())
            self.assertEqual(1, len(findings))

    def test_many_findings(self):
        with open(sample_path("many_findings.json")) as test_file:
            parser = AwsSecurityFindingFormatParser()
            findings = parser.get_findings(test_file, Test())
            self.assertEqual(3, len(findings))

    def test_repeated_findings(self):
        with open(sample_path("repeated_findings.json")) as test_file:
            parser = AwsSecurityFindingFormatParser()
            findings = parser.get_findings(test_file, Test())
            self.assertEqual(1, len(findings))
