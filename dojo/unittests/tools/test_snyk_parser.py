from django.test import TestCase
from dojo.tools.snyk.parser import SnykParser
from dojo.models import Test


class TestSnykParser(TestCase):
    def test_snykParser_single_has_no_finding(self):
        testfile = open("dojo/unittests/scans/snyk/single_project_no_vulns.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))
        testfile.close()

    def test_snykParser_allprojects_has_no_finding(self):
        testfile = open("dojo/unittests/scans/snyk/all-projects_no_vulns.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))
        testfile.close()

    def test_snykParser_single_has_one_finding(self):
        testfile = open("dojo/unittests/scans/snyk/single_project_one_vuln.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(1, len(findings))
        testfile.close()

    def test_snykParser_allprojects_has_one_finding(self):
        testfile = open("dojo/unittests/scans/snyk/all-projects_one_vuln.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_snykParser_single_has_many_findings(self):
        testfile = open("dojo/unittests/scans/snyk/single_project_many_vulns.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(41, len(findings))

    def test_snykParser_allprojects_has_many_findings(self):
        testfile = open("dojo/unittests/scans/snyk/all-projects_many_vulns.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(4, len(findings))

    def test_snykParser_finding_has_fields(self):
        testfile = open("dojo/unittests/scans/snyk/single_project_one_vuln.json")
        parser = SnykParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        finding = findings[0]
        self.assertEqual(
            "com.test:myframework@1.0.0-SNAPSHOT: XML External Entity (XXE) Injection",
            finding.title,
        )
        self.assertEqual("Medium", finding.severity)
        self.assertEqual(
            "Issue severity of: **Medium** from a base CVSS score of: **6.5**",
            finding.severity_justification,
        )
        self.assertEqual(
            "SNYK-JAVA-ORGAPACHESANTUARIO-460281", finding.vuln_id_from_tool
        )
        self.assertEqual("CVE-2019-12400", finding.cve)
        self.assertEqual(611, finding.cwe)
        self.assertEqual("AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:L", finding.cvssv3)
        self.assertEqual(
            "## Remediation\nUpgrade `org.apache.santuario:xmlsec` to version 2.1.4 or higher.\n",
            finding.mitigation,
        )
        self.assertEqual(
            "**SNYK ID**: https://app.snyk.io/vuln/SNYK-JAVA-ORGAPACHESANTUARIO-460281\n\n**GitHub "
            + "Commit**: https://github.com/apache/santuario-java/commit/52ae824cf5f5c873a0e37bb33fedcc3b387"
            + "cdba6\n**GitHub Commit**: https://github.com/apache/santuario-java/commit/c5210f77a77105fba81"
            + "311d16c07ceacc21f39d5\n**Possible Jira Issue**: https://issues.apache.org/jira/browse/SANTUARIO-"
            + "504?jql=project%20%3D%20SANTUARIO\n**Security Release**: http://santuario.apache.org/secadv.data/"
            + "CVE-2019-12400.asc?version=1&modificationDate=1566573083000&api=v2\n",
            finding.references,
        )
        self.assertEqual(
            "com.test:myframework > org.apache.santuario:xmlsec", finding.file_path
        )
