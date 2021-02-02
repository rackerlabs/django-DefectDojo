from django.test import TestCase
from dojo.tools.appspider.parser import AppSpiderXMLParser
from dojo.models import Product, Engagement, Test, Finding


class TestAppSpiderXMLParser(TestCase):
    def test_appspider_parser_has_one_finding(self):
        test = Test()
        test.engagement = Engagement()
        test.engagement.product = Product()
        testfile = open("dojo/unittests/scans/appspider/one_vuln.xml")
        parser = AppSpiderXMLParser()
        findings = parser.get_findings(testfile, test)
        testfile.close()
        self.assertEqual(1, len(findings))
        item = findings[0]
        with self.subTest(item=0):
            self.assertEqual(525, item.cwe)

    # def test_aqua_parser_has_many_findings(self):
    #     testfile = open("dojo/unittests/scans/aqua/many_vulns.json")
    #     parser = AquaJSONParser(testfile, Test())
    #     testfile.close()
    #     self.assertEqual(24, len(findings))

    def convert_severity(self):
        with self.subTest(val="0-Safe"):
            self.assertIn(
                Finding.SEVERITIES, AppSpiderXMLParser.convert_severity("0-Safe")
            )
