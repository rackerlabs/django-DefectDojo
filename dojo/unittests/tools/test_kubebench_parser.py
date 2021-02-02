from django.test import TestCase
from dojo.tools.kubebench.parser import KubeBenchParser
from dojo.models import Test


class TestKubeBenchParser(TestCase):
    def test_parse_file_with_no_vuln_has_no_findings(self):
        testfile = open(
            "dojo/unittests/scans/kubebench/kube-bench-report-zero-vuln.json"
        )
        parser = KubeBenchParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_one_vuln_has_one_finding(self):
        testfile = open(
            "dojo/unittests/scans/kubebench/kube-bench-report-one-vuln.json"
        )
        parser = KubeBenchParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_findings(self):
        testfile = open(
            "dojo/unittests/scans/kubebench/kube-bench-report-many-vuln.json"
        )
        parser = KubeBenchParser()
        findings = parser.get_findings(testfile, Test())
        self.assertTrue(len(findings) == 4)
