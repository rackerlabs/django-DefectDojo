from django.test import TestCase
from dojo.tools.factory import import_parser_factory
from dojo.models import Test


class TestFactory(TestCase):
    def test_acunetix_one_finding(self):
        testfile = open("dojo/unittests/scans/acunetix/one_finding.xml")
        parser = import_parser_factory(testfile, Test(), False, False, "Acunetix Scan")
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_anchore_one_finding(self):
        testfile = open("dojo/unittests/scans/anchore/one_vuln.json")
        parser = import_parser_factory(
            testfile, Test(), False, False, "Anchore Engine Scan"
        )
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))
