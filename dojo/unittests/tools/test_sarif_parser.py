from django.test import TestCase

from dojo.models import Test
from dojo.tools.sarif.parser import SarifParser


class TestSarifParser(TestCase):
    def test_example_report(self):
        testfile = open(
            "dojo/unittests/scans/sarif/DefectDojo_django-DefectDojo__2020-12-11_13 42 10__export.sarif"
        )
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        self.assertEqual(510, len(findings))

    def test_example2_report(self):
        testfile = open("dojo/unittests/scans/sarif/appendix_k.sarif")
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        self.assertEqual(1, len(findings))
        item = findings[0]
        self.assertEqual("collections/list.h", item.file_path)
        self.assertEqual(15, item.line)
        self.assertEqual("Critical", item.severity)
        self.assertEqual(
            "A variable was used without being initialized.", item.description
        )
        self.assertEqual(True, item.static_finding)
        self.assertEqual(False, item.dynamic_finding)

    def test_example_k1_report(self):
        testfile = open("dojo/unittests/scans/sarif/appendix_k1.sarif")
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        self.assertEqual(0, len(findings))

    def test_example_k2_report(self):
        testfile = open("dojo/unittests/scans/sarif/appendix_k2.sarif")
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        self.assertEqual(1, len(findings))
        item = findings[0]
        self.assertEqual("src/collections/list.cpp", item.file_path)
        self.assertEqual(15, item.line)
        self.assertEquals(
            "A variable was used without being initialized. This can result in runtime errors such as null reference exceptions.",
            item.description,
        )

    def test_example_k3_report(self):
        testfile = open("dojo/unittests/scans/sarif/appendix_k3.sarif")
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        self.assertEqual(1, len(findings))
        item = findings[0]
        self.assertEqual(
            'The insecure method "Crypto.Sha1.Encrypt" should not be used.', item.title
        )

    def test_example_report_ms(self):
        """Report file come from Microsoft SARIF sdk on GitHub"""
        testfile = open("dojo/unittests/scans/sarif/SuppressionTestCurrent.sarif")
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        self.assertEqual(4, len(findings))
        item = findings[0]
        self.assertEqual("New suppressed result.", item.title)

    def test_example_report_semgrep(self):
        testfile = open(
            "dojo/unittests/scans/sarif/semgrepowasp-benchmark-sample.sarif"
        )
        test = Test()
        parser = SarifParser()
        findings = parser.get_findings(testfile, test)
        self.assertIsNotNone(test.title)
        item = findings[0]
        self.assertEqual(
            "src/main/java/org/owasp/benchmark/testcode/BenchmarkTest02660.java",
            item.file_path,
        )
