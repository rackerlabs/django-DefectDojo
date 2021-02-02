from django.test import TestCase

from dojo.models import Test, Engagement, Product
from dojo.tools.contrast.parser import ContrastCSVParser


class TestContrastCSVParser(TestCase):
    def test_example_report(self):
        test = Test()
        test.engagement = Engagement()
        test.engagement.product = Product()
        testfile = open("dojo/unittests/scans/contrast/contrast-node-goat.csv")
        parser = ContrastCSVParser()
        findings = parser.get_findings(testfile, test)
        self.assertEqual(52, len(findings))
        with self.subTest(i=0):
            finding = findings[0]
            self.assertEqual("Info", finding.severity)
            self.assertEqual(
                "Forms Without Autocomplete Prevention on 2 pages", finding.title
            )
            self.assertEqual("OMEC-Y0TI-FRLE-FJQQ", finding.vuln_id_from_tool)
            self.assertEqual(522, finding.cwe)
            # endpoints
            self.assertIsNotNone(finding.unsaved_endpoints)
            self.assertEqual(1, len(finding.unsaved_endpoints))
            endpoint = finding.unsaved_endpoints[0]
            self.assertEqual("http", endpoint.protocol)
            self.assertEqual("/WebGoat/login.mvc", endpoint.path)

    def test_example2_report(self):
        test = Test()
        test.engagement = Engagement()
        test.engagement.product = Product()
        testfile = open("dojo/unittests/scans/contrast/vulnerabilities2020-09-21.csv")
        parser = ContrastCSVParser()
        findings = parser.get_findings(testfile, test)
        self.assertEqual(1, len(findings))
        with self.subTest(i=0):
            finding = findings[0]
            self.assertEqual("Medium", finding.severity)
            self.assertEqual("'MD5' hash algorithm used at Digest.java", finding.title)
            self.assertEqual("072U-8EYA-BNSH-PGN6", finding.vuln_id_from_tool)
            self.assertEqual(327, finding.cwe)
