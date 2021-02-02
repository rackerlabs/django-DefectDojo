from django.test import TestCase
from dojo.tools.h1.parser import HackerOneJSONParser
from dojo.models import Test


class TestHackerOneParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_finding(self):
        testfile = open("dojo/unittests/scans/h1/data_empty.json")
        parser = HackerOneJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_finding(self):
        testfile = open("dojo/unittests/scans/h1/data_one.json")
        parser = HackerOneJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_finding(self):
        testfile = open("dojo/unittests/scans/h1/data_many.json")
        parser = HackerOneJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(2, len(findings))
