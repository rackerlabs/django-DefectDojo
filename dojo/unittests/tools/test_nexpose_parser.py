from django.test import TestCase
from dojo.tools.nexpose.parser import NexposeFullXmlParser
from dojo.models import Test, Engagement, Product


class TestNexposeParser(TestCase):
    def test_nexpose_parser_has_no_finding(self):
        testfile = open("dojo/unittests/scans/nexpose/no_vuln.xml")
        parser = NexposeFullXmlParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_nexpose_parser_has_many_finding(self):
        test = Test()
        test.engagement = Engagement()
        test.engagement.product = Product()
        testfile = open("dojo/unittests/scans/nexpose/many_vulns.xml")
        parser = NexposeFullXmlParser()
        findings = parser.get_findings(testfile, test)
        testfile.close()
        self.assertEqual(10, len(findings))
        # vuln 1
        finding = findings[0]
        self.assertEqual("Critical", finding.severity)
        self.assertEqual('Default SSH password: root password "root"', finding.title)
        self.assertIsNone(finding.cve)
        self.assertEqual(1, len(finding.unsaved_endpoints))
        # vuln 2
        finding = findings[1]
        self.assertEqual("Medium", finding.severity)
        self.assertEqual("Missing HttpOnly Flag From Cookie", finding.title)
        self.assertIsNone(finding.cve)
        print(finding.unsaved_endpoints)
        self.assertEqual(1, len(finding.unsaved_endpoints))
