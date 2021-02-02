import sys

sys.path.append("..")
import datetime
from django.test import TestCase
from dojo.models import Test, Engagement, Product
from dojo.tools.generic.parser import GenericFindingUploadCsvParser


class TestFile(object):
    def read(self):
        return self.content

    def __init__(self, name, content):
        self.name = name
        self.content = content


class TestGenericFindingUploadCsvParser(TestCase):
    def setUp(self):
        self.product = Product(name="sample product", description="what a description")
        self.engagement = Engagement(name="sample engagement", product=self.product)
        self.test = Test(engagement=self.engagement)

    def test_parse_no_csv_content_no_findings(self):
        findings = ""
        file = TestFile("findings.csv", findings)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(0, len(findings))

    def test_parse_csv_with_only_headers_results_in_no_findings(self):
        content = "Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified"
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(0, len(findings))

    def test_parse_csv_with_single_vulnerability_results_in_single_finding(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/16,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(1, len(findings))

    def test_parse_csv_with_multiple_vulnerabilities_results_in_multiple_findings(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/16,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
11/7/16,Potential SQL Injection,112,,High,"FileName: UserData.cs
Description: Potential SQL Injection Vulnerability
Line:42
Code Line: strSQL=""SELECT * FROM users WHERE user_id="" + request_user_id",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(2, len(findings))

    def test_parse_csv_with_duplicates_results_in_single_findings(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/16,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
11/7/16,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(1, len(findings))

    def test_parsed_finding_has_date(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(datetime.date(2015, 11, 7), findings[0].date)

    def test_parsed_finding_has_title(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("Potential XSS Vulnerability", findings[0].title)

    def test_parsed_finding_has_cwe(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,,High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(79, findings[0].cwe)

    def test_parsed_finding_has_url(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("http://localhost/default.aspx", findings[0].url)

    def test_parsed_finding_has_severity(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("High", findings[0].severity)

    def test_parsed_finding_with_invalid_severity_has_info_severity(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",Unknown,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("Info", findings[0].severity)

    def test_parsed_finding_has_description(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);",None,,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(
            "FileName: default.aspx.cs\nDescription: Potential XSS Vulnerability\nLine:18\nCode Line: Response.Write(output);",
            findings[0].description,
        )

    def test_parsed_finding_has_mitigation(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available",,,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("None Currently Available", findings[0].mitigation)

    def test_parsed_finding_has_impact(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown",,TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("Impact is currently unknown", findings[0].impact)

    def test_parsed_finding_has_references(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual("Finding has references.", findings[0].references)

    def test_parsed_finding_has_positive_active_status(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",TRUE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(True, findings[0].active)

    def test_parsed_finding_has_negative_active_status(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(False, findings[0].active)

    def test_parsed_finding_has_positive_verified_status(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,TRUE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(True, findings[0].verified)

    def test_parsed_finding_has_negative_verified_status(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(False, findings[0].verified)

    def test_parsed_finding_has_positive_false_positive_status(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified,FalsePositive
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,FALSE,TRUE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(True, findings[0].false_p)

    def test_parsed_finding_has_negative_false_positive_status(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified,FalsePositive
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,FALSE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(False, findings[0].false_p)

    def test_parsed_finding_is_duplicate_has_positive_value(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified,FalsePositive,Duplicate
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,FALSE,FALSE,TRUE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(True, findings[0].duplicate)

    def test_parsed_finding_is_duplicate_has_negative_value(self):
        content = """Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified,FalsePositive,Duplicate
11/7/2015,Potential XSS Vulnerability,79,"http://localhost/default.aspx",High,"FileName: default.aspx.cs
Description: Potential XSS Vulnerability
Line:18
Code Line: Response.Write(output);","None Currently Available","Impact is currently unknown","Finding has references.",FALSE,FALSE,FALSE,FALSE
"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)
        self.assertEqual(False, findings[0].duplicate)

    def test_missing_columns_is_fine(self):
        content = """Date,Title,Url,Severity,Description,References,Active,Verified"""
        file = TestFile("findings.csv", content)
        parser = GenericFindingUploadCsvParser()
        findings = parser.get_findings(file, self.test, True, True)

    def test_column_order_is_flexible(self):
        content1 = """\
Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active,Verified
11/7/2015,Title,0,Url,Severity,Description,Mitigation,Impact,References,True,True
"""
        content2 = """\
Verified,Date,Title,CweId,Url,Severity,Description,Mitigation,Impact,References,Active
True,11/7/2015,Title,0,Url,Severity,Description,Mitigation,Impact,References,True
"""
        file1 = TestFile("findings.csv", content1)
        file2 = TestFile("findings.csv", content2)

        parser1 = GenericFindingUploadCsvParser()
        findings1 = parser1.get_findings(file1, self.test, True, True)
        parser2 = GenericFindingUploadCsvParser()
        findings2 = parser2.get_findings(file2, self.test, True, True)

        finding1 = findings1[0]
        finding2 = findings2[0]

        fields1 = {k: v for k, v in finding1.__dict__.items() if k != "_state"}
        fields2 = {k: v for k, v in finding2.__dict__.items() if k != "_state"}

        self.assertEqual(fields1, fields2)
