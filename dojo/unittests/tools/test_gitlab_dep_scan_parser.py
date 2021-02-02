from django.test import TestCase
from dojo.tools.gitlab_dep_scan.parser import GitlabDepScanReportParser
from dojo.models import Test


class TestGitlabDepScanReportParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_findings(self):
        testfile = open(
            "dojo/unittests/scans/gitlab_dep_scan/gl-dependency-scanning-report-0-vuln.json"
        )
        parser = GitlabDepScanReportParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_finding(self):
        testfile = open(
            "dojo/unittests/scans/gitlab_dep_scan/gl-dependency-scanning-report-1-vuln.json"
        )
        parser = GitlabDepScanReportParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_findings(self):
        testfile = open(
            "dojo/unittests/scans/gitlab_dep_scan/gl-dependency-scanning-report-many-vuln.json"
        )
        parser = GitlabDepScanReportParser()
        findings = parser.get_findings(testfile, Test())
        self.assertTrue(len(findings) > 2)
