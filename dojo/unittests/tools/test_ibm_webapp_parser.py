from django.test import TestCase
from dojo.models import Test
from dojo.tools.ibm_app.parser import IbmAppScanDASTXMLParser


class TestIbmAppParser(TestCase):
    def test_parse_file(self):
        testfile = open("dojo/unittests/scans/ibm_app/testfire.xml")
        parser = IbmAppScanDASTXMLParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(27, len(findings))
        finding = findings[0]
        self.assertEqual("Low", finding.severity)
        # FIXME manage CWE
        # self.assertEqual(79, finding.cwe)
        finding = findings[1]
        # FIXME fix Info/Informational drama for this parser
        self.assertEqual("Informational", finding.severity)
        # FIXME manage CWE
        # self.assertEqual(79, finding.cwe)
