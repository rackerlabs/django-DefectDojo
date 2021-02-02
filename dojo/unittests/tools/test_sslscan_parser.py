from django.test import TestCase
from dojo.tools.sslscan.parser import SslscanXMLParser
from dojo.models import Test


class TestSslscanParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_findings(self):
        testfile = open("dojo/unittests/scans/sslscan/sslscan_no_vuln.xml")
        parser = SslscanXMLParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_findings(self):
        testfile = open("dojo/unittests/scans/sslscan/sslscan_one_vuln.xml")
        parser = SslscanXMLParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_finding(self):
        testfile = open("dojo/unittests/scans/sslscan/sslscan_many_vuln.xml")
        parser = SslscanXMLParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(2, len(findings))
