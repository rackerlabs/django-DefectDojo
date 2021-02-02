from django.test import TestCase
from dojo.tools.cobalt.parser import CobaltCSVParser
from dojo.models import Test


class TestCobaltParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_findings(self):

        testfile = open("dojo/unittests/scans/cobalt/cobalt_no_vuln.csv")
        parser = CobaltCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_findings(self):
        testfile = open("dojo/unittests/scans/cobalt/cobalt_one_vuln.csv")
        parser = CobaltCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_finding(self):
        testfile = open("dojo/unittests/scans/cobalt/cobalt_many_vuln.csv")
        parser = CobaltCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(9, len(findings))
