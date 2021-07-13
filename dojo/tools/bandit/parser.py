import json
import dateutil.parser

from dojo.models import Finding


class BanditParser(object):
    def get_scan_types(self):
        return ["Bandit Scan"]

    def get_label_for_scan_types(self, scan_type):
        return "Bandit Scan"

    def get_description_for_scan_types(self, scan_type):
        return "JSON report format"

    def get_findings(self, filename, test):
        data = json.load(filename)

        dupes = dict()

        find_date = None
        if "generated_at" in data:
            find_date = dateutil.parser.parse(data["generated_at"])

        for item in data["results"]:

            findingdetail = "\n".join(
                [
                    "**Test Name:** `" + item["test_name"] + "`",
                    "**Test ID:** `" + item["test_id"] + "`",
                    "**Filename:** `" + item["filename"] + "`",
                    "**Line number:** `" + str(item["line_number"]) + "`",
                    "**Issue Confidence:** `" + item["issue_confidence"] + "`",
                    "**Code:**",
                    "```\n" +
                    str(item.get("code")).replace("```", "\\`\\`\\`") +
                    "\n```",
                ]
            )

            finding = Finding(
                title=item["issue_text"],
                test=test,
                description=findingdetail,
                severity=item["issue_severity"].title(),
                file_path=item["filename"],
                line=item["line_number"],
                date=find_date,
                static_finding=True,
                dynamic_finding=False,
                vuln_id_from_tool=":".join([item["test_name"], item["test_id"]]),
                nb_occurences=1,
            )
            # manage confidence
            if "issue_confidence" in item:
                finding.scanner_confidence = self.convert_confidence(
                    item.get("issue_confidence")
                )
            if "more_info" in item:
                finding.references = item["more_info"]

            dupe_key = finding.vuln_id_from_tool

            if dupe_key in dupes:
                find = dupes[dupe_key]
                find.file_path = None  # as there is more than one file we remove this data
                find.line = 0
                find.description += "\n-----\n\n" + finding.description
                find.nb_occurences += 1
            else:
                dupes[dupe_key] = finding

        return list(dupes.values())

    def convert_confidence(self, value):
        if "high" == value.lower():
            return 2
        elif "medium" == value.lower():
            return 3
        elif "low" == value.lower():
            return 6
        else:
            return None
