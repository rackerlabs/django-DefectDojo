from django.test import TestCase
from dojo.tools.testssl.parser import TestsslCSVParser
from dojo.models import Test


class TestTestsslCSVParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_finding(self):
        testfile = open("dojo/unittests/scans/testssl/defectdojo_no_vuln.csv")
        parser = TestsslCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_finding(self):
        testfile = open("dojo/unittests/scans/testssl/defectdojo_one_vuln.csv")
        parser = TestsslCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_many_vuln_has_many_findings(self):
        testfile = open("dojo/unittests/scans/testssl/defectdojo_many_vuln.csv")
        parser = TestsslCSVParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(99, len(findings))
