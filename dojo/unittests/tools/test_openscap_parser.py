from django.test import TestCase
from dojo.tools.openscap.parser import OpenscapXMLParser
from dojo.models import Test


class TestOpenscapXMLParser(TestCase):
    def test_openscap_parser_with_no_vuln_has_no_findings(self):
        testfile = open("dojo/unittests/scans/openscap/no_vuln_rhsa.xml")
        parser = OpenscapXMLParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(0, len(findings))

    def test_openscap_parser_with_one_criticle_vuln_has_one_findings(self):
        testfile = open("dojo/unittests/scans/openscap/one_vuln_rhsa.xml")
        parser = OpenscapXMLParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_openscap_parser_with_many_vuln_has_many_findings(self):
        testfile = open("dojo/unittests/scans/openscap/many_vuln_rhsa.xml")
        parser = OpenscapXMLParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(31, len(findings))
