from django.test import TestCase
from dojo.tools.ossindex_devaudit.parser import OssIndexDevauditParser
from dojo.models import Test


class TestOssIndexDevauditParser(TestCase):
    def test_ossindex_devaudit_parser_with_no_vulns_has_no_findings(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_no_vuln.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(0, len(findings))

    def test_ossindex_devaudit_parser_with_one_critical_vuln_has_one_finding(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_one_vuln.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_ossindex_devaudit_parser_with_multiple_vulns_has_multiple_finding(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_multiple_vulns.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertTrue(len(findings) > 1)

    def test_ossindex_devaudit_parser_with_no_cve_returns_info_severity(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_vuln_no_cvssscore.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertTrue(len(findings) == 1)

    def test_ossindex_devaudit_parser_with_reference_shows_reference(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_one_vuln.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()

        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.references != "")

    def test_ossindex_devaudit_parser_with_empty_reference_shows_empty_reference(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_empty_reference.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.references == "")

    def test_ossindex_devaudit_parser_with_missing_reference_shows_empty(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_missing_reference.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.references == "")

    def test_ossindex_devaudit_parser_with_missing_cwe_shows_1035(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_missing_cwe.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.cwe == 1035)

    def test_ossindex_devaudit_parser_with_null_cwe_shows_1035(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_null_cwe.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.cwe == 1035)

    def test_ossindex_devaudit_parser_with_empty_cwe_shows_1035(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_empty_cwe.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.cwe == 1035)

    def test_ossindex_devaudit_parser_get_severity_shows_info(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_severity_info.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.severity == "Info")

    def test_ossindex_devaudit_parser_get_severity_shows_critical(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_severity_critical.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.severity == "Critical")

    def test_ossindex_devaudit_parser_get_severity_shows_high(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_severity_high.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.severity == "High")

    def test_ossindex_devaudit_parser_get_severity_shows_medium(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_severity_medium.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.severity == "Medium")

    def test_ossindex_devaudit_parser_get_severity_shows_low(self):
        testfile = open(
            "dojo/unittests/scans/ossindex_devaudit_sample/ossindex_devaudit_severity_low.json"
        )
        parser = OssIndexDevauditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        if len(findings) > 0:
            for item in findings:
                self.assertTrue(item.severity == "Low")
