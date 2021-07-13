import datetime
from dateutil.tz import tzlocal
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
        with self.subTest(i=0):
            item = findings[0]
            self.assertEqual("Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.", item.title)
            self.assertEqual(datetime.datetime(2020, 12, 30, 10, 3, 39, tzinfo=tzlocal()), item.date)
            self.assertEqual("Low", item.severity)
            self.assertEqual("one/one.py", item.file_path)
            self.assertEqual('assert_used:B101', item.vuln_id_from_tool)
            self.assertEqual("Certain", item.get_scanner_confidence_text())
            self.assertEqual(1, item.nb_occurences)
            self.assertIn("B101", item.references.upper())

    def test_bandit_parser_has_many_findings(self):
        testfile = open("dojo/unittests/scans/bandit/many_vulns.json")
        parser = BanditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(16, len(findings))
        with self.subTest(i=0):
            item = findings[0]
            self.assertEqual("Try, Except, Pass detected.", item.title)
            self.assertEqual(datetime.datetime(2020, 12, 30, 9, 35, 48, tzinfo=tzlocal()), item.date)
            self.assertEqual("Low", item.severity)
            self.assertEqual('try_except_pass:B110', item.vuln_id_from_tool)
            self.assertEqual("Certain", item.get_scanner_confidence_text())
            self.assertEqual(20, item.nb_occurences)
            self.assertIn("B110", item.references.upper())

    def test_bandit_parser_has_many_findings_recent(self):
        testfile = open("dojo/unittests/scans/bandit/dd.json")
        parser = BanditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(8, len(findings))
        with self.subTest(i=0):
            item = findings[0]
            self.assertEqual("Use of insecure MD2, MD4, MD5, or SHA1 hash function.", item.title)
            self.assertEqual(datetime.datetime(2021, 3, 30, 18, 23, 12, tzinfo=tzlocal()), item.date)
            self.assertEqual("Medium", item.severity)
            self.assertEqual('blacklist:B303', item.vuln_id_from_tool)
            self.assertEqual("Certain", item.get_scanner_confidence_text())
            self.assertEqual(30, item.nb_occurences)
            self.assertIn("B303", item.references.upper())

    def test_bandit_parser_has_many_findings_big(self):
        testfile = open("dojo/unittests/scans/bandit/kolibri_0_14_7.json")
        parser = BanditParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(43, len(findings))
        with self.subTest(i=0):
            item = findings[0]
            self.assertEqual("Try, Except, Pass detected.", item.title)
            self.assertEqual(datetime.datetime(2021, 6, 18, 21, 46, 58, tzinfo=tzlocal()), item.date)
            self.assertEqual("Low", item.severity)
            self.assertEqual('try_except_pass:B110', item.vuln_id_from_tool)
            self.assertEqual("Certain", item.get_scanner_confidence_text())
            self.assertEqual(78, item.nb_occurences)
            self.assertIn("B110", item.references.upper())
