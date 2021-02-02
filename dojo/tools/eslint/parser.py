__author__ = "omerlh"

import json

from dojo.models import Finding


class ESLintParser(object):
    def _convert_eslint_severity_to_dojo_severity(self, eslint_severity):
        if eslint_severity == 2:
            return "High"
        elif eslint_severity == 1:
            return "Medium"
        else:
            return None

    def get_findings(self, filename, test):
        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)

        items = list()
        for item in data:
            findingdetail = ""

            if len(item["messages"]) == 0:
                continue

            for message in item["messages"]:

                if message["message"] is None:
                    title = str("Finding Not defined")
                else:
                    title = str(message["message"])

                if message["ruleId"] is not None:
                    title = title + " Test ID: " + str(message["ruleId"])

                findingdetail += "Filename: " + item["filePath"] + "\n"
                findingdetail += "Line number: " + str(message["line"]) + "\n"

                sev = self._convert_eslint_severity_to_dojo_severity(
                    message["severity"]
                )

                find = Finding(
                    title=title,
                    test=test,
                    active=False,
                    verified=False,
                    description=findingdetail,
                    severity=sev.title(),
                    numerical_severity=Finding.get_numerical_severity(sev),
                    file_path=item["filePath"],
                    line=message["line"],
                    url="N/A",
                    static_finding=True,
                    mitigation="N/A",
                    impact="N/A",
                )

                items.append(find)
        return items
