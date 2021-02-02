__author__ = "Spoint42"

import json

from dojo.models import Finding


class DrHeaderJSONParser(object):
    def _convert_drheader_severity_to_dojo_severity(self, drheader_severity):
        if drheader_severity == "high":
            return "High"
        elif drheader_severity == "medium":
            return "Medium"
        else:
            return None

    def get_findings(self, filename, test):
        items = []
        if filename is None:
            return
        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)

        for item in data:
            findingdetail = ""
            title = "Header : " + item["rule"]
            sev = self._convert_drheader_severity_to_dojo_severity(item["severity"])
            message = item["message"]

            find = Finding(
                title=title,
                test=test,
                active=True,
                verified=True,
                description=message,
                severity=sev.title(),
                numerical_severity=Finding.get_numerical_severity(sev),
                static_finding=False,
            )

            items.append(find)
        return items
