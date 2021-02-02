from django.test import TestCase
from dojo.tools.huskyci.parser import HuskyCIReportParser
from dojo.models import Test


class TestHuskyCIReportParser(TestCase):
    def test_parse_file_no_finding(self):
        testfile = open("dojo/unittests/scans/huskyci/huskyci_report_no_finding.json")
        parser = HuskyCIReportParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_has_one_finding_one_tool(self):
        testfile = open(
            "dojo/unittests/scans/huskyci/huskyci_report_one_finding_one_tool.json"
        )
        parser = HuskyCIReportParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_parse_file_has_many_finding_one_tool(self):
        testfile = open(
            "dojo/unittests/scans/huskyci/huskyci_report_many_finding_one_tool.json"
        )
        parser = HuskyCIReportParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(3, len(findings))

    def test_parse_file_has_many_finding_two_tools(self):
        testfile = open(
            "dojo/unittests/scans/huskyci/huskyci_report_many_finding_two_tools.json"
        )
        parser = HuskyCIReportParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(15, len(findings))
