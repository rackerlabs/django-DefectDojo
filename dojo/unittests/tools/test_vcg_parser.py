import io
import csv

from defusedxml import ElementTree
from django.test import TestCase

from dojo.models import Test
from dojo.tools.vcg.parser import VCGCsvParser
from dojo.tools.vcg.parser import VCGParser
from dojo.tools.vcg.parser import VCGXmlParser


class TestFile(object):
    def read(self):
        return self.content

    def __init__(self, name, content):
        self.name = name
        self.content = content


class TestVCGXmlParser(TestCase):
    def setUp(self):
        self.parser = VCGXmlParser()

    def test_parse_no_content_no_findings(self):
        results = self.parser.parse(None, Test())
        self.assertEqual(0, len(results))

    def test_parse_single_finding(self):
        single_finding = """<?xml version="1.0" encoding="utf-8"?>
        <!--XML Export of VCG Results for directory: C:\\Projects\\WebGoat.Net. Scanned for C# security issues.-->
        <CodeIssueCollection>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>21</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        </CodeIssueCollection>"""

        results = self.parser.parse(single_finding, Test())
        self.assertEqual(1, len(results))

    def test_parse_multiple_findings(self):
        findings = """<?xml version="1.0" encoding="utf-8"?>
        <!--XML Export of VCG Results for directory: C:\\Projects\\WebGoat.Net. Scanned for C# security issues.-->
        <CodeIssueCollection>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>21</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>62</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        </CodeIssueCollection>"""

        results = self.parser.parse(findings, Test())
        self.assertEqual(2, len(results))

    def test_parse_duplicate_findings_dedupes(self):
        duplicate_finding = """<?xml version="1.0" encoding="utf-8"?>
        <!--XML Export of VCG Results for directory: C:\\Projects\\WebGoat.Net. Scanned for C# security issues.-->
        <CodeIssueCollection>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>21</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>21</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        </CodeIssueCollection>"""

        results = self.parser.parse(duplicate_finding, Test())
        self.assertEqual(1, len(results))

    def test_parseissuexml_with_no_issue_has_no_finding(self):
        self.assertIsNone(self.parser.parse_issue(None, Test()))

    def test_parseissuexml_with_issue_has_finding(self):
        single_finding = """<?xml version="1.0" encoding="utf-8"?>
        <!--XML Export of VCG Results for directory: C:\\Projects\\WebGoat.Net. Scanned for C# security issues.-->
        <CodeIssueCollection>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>21</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        </CodeIssueCollection>"""

        vcgscan = ElementTree.fromstring(single_finding)
        finding = self.parser.parse_issue(vcgscan.findall("CodeIssue")[0], Test())
        self.assertEqual("Info", finding.severity)
        self.assertEqual("S4", finding.numerical_severity)
        self.assertEqual("Comment Indicates Potentially Unfinished Code", finding.title)


class TestVCGCsvParser(TestCase):
    def setUp(self):
        self.parser = VCGCsvParser()

    def test_parse_no_csv_content_no_findings(self):
        findings = ""
        results = self.parser.parse(findings, Test())
        self.assertEqual(0, len(results))

    def test_parse_single_finding_single_result(self):
        findings = (
            """6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,16,"TODO: Refactor this. Use LINQ with aggregation to get SUM.",False,"LawnGreen"""
            ""
        )
        results = self.parser.parse(findings, Test())
        self.assertEqual(1, len(results))

    def test_parse_multiple_findings_multiple_results(self):
        findings = (
            """6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,16,"TODO: Refactor this. Use LINQ with aggregation to get SUM.",False,"LawnGreen"
6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,41,"TODO: Add ability to delete an orderDetail and to change quantities.",False,"LawnGreen"""
            ""
        )
        results = self.parser.parse(findings, Test())
        self.assertEqual(2, len(results))

    def test_parse_duplicate_findings_deduped_results(self):
        findings = (
            """6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,16,"TODO: Refactor this. Use LINQ with aggregation to get SUM.",False,"LawnGreen"
6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,16,"TODO: Refactor this. Use LINQ with aggregation to get SUM.",False,"LawnGreen"""
            ""
        )
        results = self.parser.parse(findings, Test())
        self.assertEqual(1, len(results))

    def test_parseissuerow_with_no_row_has_no_finding(self):
        finding = self.parser.parse_issue(None, Test())
        self.assertIsNone(finding)

    def test_parseissuerow_with_empty_row_has_no_finding(self):
        row = dict()
        finding = self.parser.parse_issue(row, Test())
        self.assertIsNone(finding)

    def test_parseissuerow_with_row_has_finding(self):
        findings = (
            """6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,16,"TODO: Refactor this. Use LINQ with aggregation to get SUM.",False,"LawnGreen"""
            ""
        )
        reader = csv.reader(io.StringIO(findings), delimiter=",", quotechar='"')
        finding = None
        for row in reader:
            finding = self.parser.parse_issue(row, Test())

        self.assertIsNotNone(finding)
        self.assertEqual("Info", finding.severity)
        self.assertEqual("S4", finding.numerical_severity)
        self.assertEqual("Comment Indicates Potentially Unfinished Code", finding.title)


class TestVCGImport(TestCase):
    def test_can_parse_xml(self):
        content = """<?xml version="1.0" encoding="utf-8"?>
        <!--XML Export of VCG Results for directory: C:\\Projects\\WebGoat.Net. Scanned for C# security issues.-->
        <CodeIssueCollection>
        <CodeIssue>
        <Priority>6</Priority>
        <Severity>Suspicious Comment</Severity>
        <Title>Comment Indicates Potentially Unfinished Code</Title>
        <Description>The comment includes some wording which indicates that the developer regards
        it as unfinished or does not trust it to work correctly.</Description>
        <FileName>Findings.xml</FileName>
        <Line>21</Line>
        <CodeLine>TODO: Check the Code</CodeLine>
        <Checked>False</Checked>
        <CheckColour>LawnGreen</CheckColour>
        </CodeIssue>
        </CodeIssueCollection>"""
        filename = TestFile("data.xml", content)
        parser = VCGParser()
        findings = parser.get_findings(filename, Test())
        self.assertEqual(1, len(findings))

    def test_can_parse_csv(self):
        content = (
            """6,Suspicious Comment,"Comment Indicates Potentially Unfinished Code","The comment includes some wording which indicates that the developer regards it as unfinished or does not trust it to work correctly.",C:\\Projects\\WebGoat.Net\\Core\\Cart.cs,16,"TODO: Refactor this. Use LINQ with aggregation to get SUM.",False,"LawnGreen"""
            ""
        )
        filename = TestFile("data.csv", content)
        parser = VCGParser()
        findings = parser.get_findings(filename, Test())
        self.assertEqual(1, len(findings))
