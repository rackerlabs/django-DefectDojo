from django.test import TestCase
from dojo.tools.bandit.parser import BanditParser
from dojo.models import Test


class TestBanditParser(TestCase):
    def test_bandit_parser_has_no_finding(self):
        testfile = open("dojo/unittests/scans/bandit/no_vuln.json")
        parser = BanditParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_bandit_parser_has_one_finding(self):
        testfile = open("dojo/unittests/scans/bandit/one_vuln.json")
        parser = BanditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_bandit_parser_has_many_findings(self):
        testfile = open("dojo/unittests/scans/bandit/many_vulns.json")
        parser = BanditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(213, len(findings))
        item = findings[0]
        self.assertEqual("Low", item.severity)
