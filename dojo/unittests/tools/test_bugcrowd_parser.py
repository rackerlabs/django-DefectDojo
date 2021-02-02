from django.test import TestCase
from dojo.tools.bugcrowd.parser import BugCrowdCSVParser
from dojo.models import Test


class TestBugCrowdParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_findings(self):
        testfile = open("dojo/unittests/scans/bugcrowd/BugCrowd-zero.csv")
        parser = BugCrowdCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_findings(self):
        testfile = open("dojo/unittests/scans/bugcrowd/BugCrowd-one.csv")
        parser = BugCrowdCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_finding(self):
        testfile = open("dojo/unittests/scans/bugcrowd/BugCrowd-many.csv")
        parser = BugCrowdCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(5, len(findings))
