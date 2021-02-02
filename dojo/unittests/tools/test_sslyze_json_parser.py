from django.test import TestCase
from dojo.tools.sslyze.parser_json import SSLyzeJSONParser
from dojo.models import Test


class TestSslyzeJSONParser(TestCase):
    def test_parse_file_with_one_target_has_zero_vuln(self):
        testfile = open("dojo/unittests/scans/sslyze/one_target_zero_vuln.json")
        parser = SSLyzeJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_target_has_one_vuln(self):
        testfile = open("dojo/unittests/scans/sslyze/one_target_one_vuln.json")
        parser = SSLyzeJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_one_target_has_four_vuln(self):
        testfile = open("dojo/unittests/scans/sslyze/one_target_many_vuln.json")
        parser = SSLyzeJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(4, len(findings))

    def test_parse_file_with_two_target_has_many_vuln(self):
        testfile = open("dojo/unittests/scans/sslyze/two_targets_two_vuln.json")
        parser = SSLyzeJSONParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(2, len(findings))
