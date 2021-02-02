import csv
import hashlib
import io

from defusedxml import ElementTree

from dojo.models import Finding


class VCGFinding(object):
    def get_finding_severity(self):
        return self.priority_mapping[self.priority]

    def get_finding_detail(self):
        finding_detail = ""

        if self.severity is not None:
            finding_detail = "Severity: " + self.severity + "\n"

        if self.description is not None:
            finding_detail += "Description: " + self.description + "\n"

        if self.filename is not None:
            finding_detail += "FileName: " + self.filename + "\n"

        if self.line is not None:
            finding_detail += "Line: " + self.line + "\n"

        if self.code_line is not None:
            finding_detail += "CodeLine: " + self.code_line + "\n"

        return finding_detail

    def to_finding(self, test):

        return Finding(
            title=self.title,
            test=test,
            active=False,
            verified=False,
            description=self.get_finding_detail(),
            severity=self.get_finding_severity(),
            numerical_severity=Finding.get_numerical_severity(
                self.get_finding_severity()
            ),
        )

    def __init__(self):
        self.priority = 6
        self.title = ""
        self.severity = ""
        self.description = ""
        self.filename = ""
        self.line = ""
        self.code_line = ""
        self.priority_mapping = dict()
        self.priority_mapping[1] = "Critical"
        self.priority_mapping[2] = "High"
        self.priority_mapping[3] = "Medium"
        self.priority_mapping[4] = "Low"
        self.priority_mapping[5] = "Low"
        self.priority_mapping[6] = "Info"
        self.priority_mapping[7] = "Info"


class VCGXmlParser(object):
    @staticmethod
    def get_field_from_xml(issue, field):
        if issue.find(field) is not None and issue.find(field).text is not None:
            return issue.find(field).text
        else:
            return None

    def __init__(self):
        pass

    def parse_issue(self, issue, test):

        if issue is None:
            return None

        data = VCGFinding()

        if self.get_field_from_xml(issue, "Priority") is None:
            data.priority = 6
        else:
            data.priority = int(float(self.get_field_from_xml(issue, "Priority")))

        data.title = (
            ""
            if self.get_field_from_xml(issue, "Title") is None
            else self.get_field_from_xml(issue, "Title")
        )
        data.severity = self.get_field_from_xml(issue, "Severity")
        data.description = self.get_field_from_xml(issue, "Description")
        data.filename = self.get_field_from_xml(issue, "FileName")
        # data.file_path = self.get_field_from_xml(issue, 'FileName')
        data.line = self.get_field_from_xml(issue, "Line")
        data.code_line = self.get_field_from_xml(issue, "CodeLine")
        # data.line = self.get_field_from_xml(issue, 'CodeLine')

        finding = data.to_finding(test)
        return finding

    def parse(self, content, test):

        dupes = dict()

        if content is None:
            return dupes

        vcgscan = ElementTree.fromstring(content)

        for issue in vcgscan.findall("CodeIssue"):
            finding = self.parse_issue(issue, test)

            if finding is not None:
                key = hashlib.md5(
                    (
                        finding.severity
                        + "|"
                        + finding.title
                        + "|"
                        + finding.description
                    ).encode("utf-8")
                ).hexdigest()

                if key not in dupes:
                    dupes[key] = finding

        return dupes


class VCGCsvParser(object):
    @staticmethod
    def get_field_from_row(row, column):
        if row[column] is not None:
            return row[column]
        else:
            return None

    def parse_issue(self, row, test):

        if not row:
            return None

        priority_column = 0
        severity_column = 1
        title_column = 2
        description_column = 3
        filename_column = 4
        line_column = 5
        code_line_column = 6

        data = VCGFinding()

        if self.get_field_from_row(row, title_column) is None:
            data.title = ""
        else:
            data.title = self.get_field_from_row(row, title_column)

        if self.get_field_from_row(row, priority_column) is None:
            data.priority = 6
        else:
            data.priority = int(float(self.get_field_from_row(row, priority_column)))

        data.severity = self.get_field_from_row(row, severity_column)
        data.description = self.get_field_from_row(row, description_column)
        data.filename = self.get_field_from_row(row, filename_column)
        data.line = self.get_field_from_row(row, line_column)
        data.code_line = self.get_field_from_row(row, code_line_column)

        finding = data.to_finding(test)
        return finding

    def parse(self, content, test):
        dupes = dict()
        if type(content) is bytes:
            content = content.decode("utf-8")
        reader = csv.reader(io.StringIO(content), delimiter=",", quotechar='"')
        for row in reader:
            finding = self.parse_issue(row, test)

            if finding is not None:
                key = hashlib.md5(
                    (
                        finding.severity
                        + "|"
                        + finding.title
                        + "|"
                        + finding.description
                    ).encode("utf-8")
                ).hexdigest()

                if key not in dupes:
                    dupes[key] = finding

        return dupes

    def __init__(self):
        pass


class VCGParser(object):
    """VCG (VisualCodeGrepper) support CSV and XML"""

    def get_findings(self, filename, test):

        if filename is None:
            return list()

        content = filename.read()

        if filename.name.lower().endswith(".xml"):
            return list(VCGXmlParser().parse(content, test).values())
        elif filename.name.lower().endswith(".csv"):
            return list(VCGCsvParser().parse(content, test).values())
        else:
            raise Exception("Unknown File Format")
