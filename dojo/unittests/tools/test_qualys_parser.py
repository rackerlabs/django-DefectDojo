from django.test import TestCase

from dojo.models import Test
from dojo.tools.qualys.parser import QualysParser


class TestQualysParser(TestCase):

    def test_parse_file_with_no_vuln_has_no_findings(self):
        testfile = open(
            "dojo/unittests/scans/qualys/empty.xml"
        )
        parser = QualysParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_multiple_vuln_has_multiple_findings(self):
        testfile = open(
            "dojo/unittests/scans/qualys/Qualys_Sample_Report.xml"
        )
        parser = QualysParser()
        findings = parser.get_findings(testfile, Test())
        for finding in findings:
            for endpoint in finding.unsaved_endpoints:
                endpoint.clean()
        self.assertEqual(301, len(findings))

        finding = findings[0]
        self.assertEqual(
            finding.title, "QID-6 | DNS Host Name"
        )
        self.assertEqual(
            finding.severity, "Informational"
        )
        self.assertEqual(
            finding.unsaved_endpoints[0].host, "demo13.s02.sjc01.qualys.com"
        )
        for finding in findings:
            if finding.unsaved_endpoints[
                0].host == "demo14.s02.sjc01.qualys.com" and finding.title == "QID-370876 | AMD Processors Multiple " \
                                                                              "Security Vulnerabilities (" \
                                                                              "RYZENFALL/MASTERKEY/CHIMERA-FW/FALLOUT)":
                finding_cvssv3_score = finding
            if finding.unsaved_endpoints[
                0].host == "demo13.s02.sjc01.qualys.com" and finding.title == "QID-370876 | AMD Processors Multiple " \
                                                                              "Security Vulnerabilities (" \
                                                                              "RYZENFALL/MASTERKEY/CHIMERA-FW/FALLOUT)":
                finding_cvssv3_vector = finding
        self.assertEqual(
            # CVSS_FINAL is defined without a cvssv3 vector
            finding_cvssv3_score.cvssv3, None
        )
        self.assertEqual(
            finding_cvssv3_score.severity, "High"
        )
        self.assertEqual(
            finding_cvssv3_vector.cvssv3, "CVSS:3.0/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H"
        )
        self.assertEqual(
            finding_cvssv3_vector.severity, "Critical"
        )

    def test_parse_file_with_multiple_vuln_has_multiple_findings_csv(self):
        testfile = open(
            "dojo/unittests/scans/qualys/Qualys_Sample_Report.csv"
        )
        parser = QualysParser()
        findings = parser.get_findings(testfile, Test())
        for finding in findings:
            for endpoint in finding.unsaved_endpoints:
                endpoint.clean()
        self.assertEqual(6, len(findings))

        finding = findings[0]
        self.assertEqual(
            finding.title, "QID-105971 | EOL/Obsolete Software: Microsoft ASP.NET 1.0 Detected"
        )
        self.assertEqual(
            finding.severity, "Critical"
        )
        self.assertEquals(
            finding.mitigation, '''Upgrade to the latest supported Microsoft ASP.NET. Refer to dotnet-core (https://docs.microsoft.com/en-us/lifecycle/products/microsoft-net-and-net-core).'''
        )
        self.assertEquals(
            finding.impact, '''The system is at high risk of being exposed to security vulnerabilities. Since the vendor no longer provides updates, obsolete software is more vulnerable to viruses and other attacks.'''
        )
        self.assertEqual(
            finding.cvssv3_score, '7.4'
        )
        self.assertEqual(
            finding.vuln_id_from_tool, '105971'
        )
        self.assertEqual(
            finding.unsaved_endpoints[0].host, "10.98.57.180"
        )
        self.assertEqual(
            finding.active, True
        )
