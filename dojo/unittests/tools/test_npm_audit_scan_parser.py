from django.test import TestCase
from dojo.tools.npm_audit.parser import NpmAuditParser
from dojo.models import Test


class TestNpmAuditParser(TestCase):
    def test_npm_audit_parser_with_no_vuln_has_no_findings(self):
        testfile = open("dojo/unittests/scans/npm_audit_sample/no_vuln.json")
        parser = NpmAuditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(0, len(findings))

    def test_npm_audit_parser_with_one_criticle_vuln_has_one_findings(self):
        testfile = open("dojo/unittests/scans/npm_audit_sample/one_vuln.json")
        parser = NpmAuditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))
        self.assertEqual("growl", findings[0].component_name)
        self.assertEqual("1.9.2", findings[0].component_version)

    def test_npm_audit_parser_with_many_vuln_has_many_findings(self):
        testfile = open("dojo/unittests/scans/npm_audit_sample/many_vuln.json")
        parser = NpmAuditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(5, len(findings))
        # TODO ordering seems to be different in ci compared to local, so disable for now
        # self.assertEqual('mime', findings[4].component_name)
        # self.assertEqual('1.3.4', findings[4].component_version)

    def test_npm_audit_parser_empty_with_error(self):
        with self.assertRaises(ValueError) as context:
            testfile = open(
                "dojo/unittests/scans/npm_audit_sample/empty_with_error.json"
            )
            parser = NpmAuditParser()
            findings = parser.get_findings(testfile, Test())
            testfile.close()
            self.assertTrue(
                "npm audit report contains errors:" in str(context.exception)
            )
            self.assertTrue("ENOAUDIT" in str(context.exception))

    def test_npm_audit_parser_many_vuln_npm7(self):
        with self.assertRaises(ValueError) as context:
            testfile = open("dojo/unittests/scans/npm_audit_sample/many_vuln_npm7.json")
            parser = NpmAuditParser()
            findings = parser.get_findings(testfile, Test())
            testfile.close()
            self.assertTrue(
                "npm7 with auditReportVersion 2 or higher not yet supported"
                in str(context.exception)
            )
            self.assertEqual(findings, None)
