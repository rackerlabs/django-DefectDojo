import json
import math

from dojo.models import Finding


class PhpSecurityAuditV2(object):
    def get_findings(self, filename, test):
        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)
        dupes = dict()

        for filepath, report in list(data["files"].items()):
            errors = report.get("errors") or 0
            warns = report.get("warnings") or 0
            if errors + warns > 0:
                for issue in report["messages"]:
                    title = issue["source"]

                    findingdetail = "Filename: " + filepath + "\n"
                    findingdetail += "Line: " + str(issue["line"]) + "\n"
                    findingdetail += "Column: " + str(issue["column"]) + "\n"
                    findingdetail += "Rule Source: " + issue["source"] + "\n"
                    findingdetail += "Details: " + issue["message"] + "\n"

                    sev = PhpSecurityAuditV2.get_severity_word(issue["severity"])

                    dupe_key = (
                        title + filepath + str(issue["line"]) + str(issue["column"])
                    )

                    if dupe_key in dupes:
                        find = dupes[dupe_key]
                    else:
                        dupes[dupe_key] = True

                        find = Finding(
                            title=title,
                            test=test,
                            active=False,
                            verified=False,
                            description=findingdetail,
                            severity=sev.title(),
                            numerical_severity=Finding.get_numerical_severity(sev),
                            mitigation="",
                            impact="",
                            references="",
                            file_path=filepath,
                            url="N/A",
                            static_finding=True,
                        )

                        dupes[dupe_key] = find
                        findingdetail = ""

        self.items = list(dupes.values())

    @staticmethod
    def get_severity_word(severity):
        sev = math.ceil(severity / 2)

        if sev == 5:
            return "Critical"
        elif sev == 4:
            return "High"
        elif sev == 3:
            return "Medium"
        else:
            return "Low"
