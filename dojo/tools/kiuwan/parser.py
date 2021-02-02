import csv
import hashlib
import io

from dojo.models import Finding

__author__ = "dr3dd589"


class Severityfilter:
    def __init__(self):
        self.severity_mapping = {
            "Very Low": "Info",
            "Low": "Low",
            "Normal": "Medium",
            "High": "High",
            "Very High": "Critical",
        }
        self.severity = None

    def eval_column(self, column_value):
        if column_value in list(self.severity_mapping.keys()):
            self.severity = self.severity_mapping[column_value]
        else:
            self.severity = "Info"


class KiuwanCSVParser(object):
    def get_findings(self, filename, test):
        content = filename.read()
        if type(content) is bytes:
            content = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter=",", quotechar='"')
        csvarray = []

        for row in reader:
            csvarray.append(row)

        dupes = dict()
        for row in csvarray:
            finding = Finding(test=test)
            findingdict = {}
            severityfilter = Severityfilter()
            severityfilter.eval_column(row["Priority"])
            findingdict["severity"] = severityfilter.severity
            findingdict["title"] = row["Rule"]
            findingdict["file"] = row["File"]
            findingdict["line_number"] = row["Line number"]
            findingdict["description"] = (
                "**Vulnerability type** : "
                + row["Vulnerability type"]
                + "\n\n"
                + "**CWE Scope** : "
                + row["CWE Scope"]
                + "\n\n"
                + "**Line number** : "
                + row["Line number"]
                + "\n\n"
                + "**Code at line number** : "
                + row["Line text"]
                + "\n\n"
                + "**Normative** : "
                + row["Normative"]
                + "\n\n"
                + "**Rule code** : "
                + row["Rule code"]
                + "\n\n"
                + "**Status** : "
                + row["Status"]
                + "\n\n"
                + "**Source file** : "
                + row["Source file"]
                + "\n\n"
                + "**Source line number** : "
                + row["Source line number"]
                + "\n\n"
                + "**Code at sorce line number** : "
                + row["Source line text"]
                + "\n"
            )

            finding.title = findingdict["title"]
            finding.file_path = findingdict["file"]
            finding.line = findingdict["line_number"]
            finding.description = findingdict["description"]
            finding.references = "Not provided!"
            finding.mitigation = "Not provided!"
            finding.severity = findingdict["severity"]
            finding.static_finding = True
            try:
                finding.cwe = int(row["CWE"])
            except:
                pass

            if finding is not None:
                if finding.title is None:
                    finding.title = ""
                if finding.description is None:
                    finding.description = ""

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

        return list(dupes.values())
