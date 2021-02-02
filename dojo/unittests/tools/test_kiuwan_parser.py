from django.test import TestCase
from dojo.tools.kiuwan.parser import KiuwanCSVParser
from dojo.models import Test


class TestKiuwanParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_findings(self):

        testfile = open("dojo/unittests/scans/kiuwan_sample/kiuwan_no_vuln.csv")
        parser = KiuwanCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_two_vuln_has_two_findings(self):
        testfile = open("dojo/unittests/scans/kiuwan_sample/kiuwan_two_vuln.csv")
        parser = KiuwanCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(2, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_finding(self):
        testfile = open("dojo/unittests/scans/kiuwan_sample/kiuwan_many_vuln.csv")
        parser = KiuwanCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(131, len(findings))
