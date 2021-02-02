from django.test import TestCase
from dojo.tools.drheader.parser import DrHeaderJSONParser
from dojo.models import Test


class TestDrHeaderJSONParser(TestCase):
    def test_parse_file_has_many_finding_one_tool(self):
        testfile = open("dojo/unittests/scans/drheader/scan.json")
        parser = DrHeaderJSONParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(6, len(findings))
