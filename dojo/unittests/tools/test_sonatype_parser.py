from os import path

from django.test import TestCase
from dojo.models import Test
from dojo.tools.sonatype.parser import SonatypeParser


class TestSonatypeParser(TestCase):
    def test_parse_file_with_one_vuln(self):
        testfile = open(path.join(path.dirname(__file__), "scans/sonatype/one_vuln.json"))
        parser = SonatypeParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_parse_file_with_many_vulns(self):
        testfile = open(path.join(path.dirname(__file__), "scans/sonatype/many_vulns.json"))
        parser = SonatypeParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(3, len(findings))

    def test_parse_file_with_long_file_path(self):
        testfile = open(path.join(path.dirname(__file__), "scans/sonatype/long_file_path.json"))
        parser = SonatypeParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(2, len(findings))
