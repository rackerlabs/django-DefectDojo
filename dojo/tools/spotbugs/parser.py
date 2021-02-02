__author__ = "bakalor"
__maintainer__ = "Igor Bakalo"
__email__ = "bigorigor.ua@gmail.com"
__status__ = "Development"

import re

from defusedxml import ElementTree as ET

from dojo.models import Finding


class SpotbugsXMLParser(object):
    def get_findings(self, filename, test):
        bug_patterns = dict()
        dupes = dict()

        SEVERITY = {"1": "High", "2": "Medium", "3": "Low"}

        tree = ET.parse(filename)
        root = tree.getroot()

        for pattern in root.findall("BugPattern"):
            plain_pattern = re.sub(
                r"<[b-z/]*?>|<a|</a>|href=",
                "",
                ET.tostring(pattern.find("Details"), method="text").decode("utf-8"),
            )
            bug_patterns[pattern.get("type")] = plain_pattern

        for bug in root.findall("BugInstance"):
            desc = ""
            for message in bug.itertext():
                desc += message

            dupe_key = bug.get("instanceHash")

            title = bug.find("ShortMessage").text
            cwe = bug.get("cweid", default=0)
            severity = SEVERITY[bug.get("priority")]
            description = desc
            mitigation = bug_patterns[bug.get("type")]
            impact = "N/A"
            references = "N/A"

            if dupe_key in dupes:
                finding = dupes[dupe_key]
            else:
                finding = Finding(
                    title=title,
                    cwe=cwe,
                    severity=severity,
                    description=description,
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    test=test,
                    active=False,
                    verified=False,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    static_finding=True,
                )
                dupes[dupe_key] = finding

        self.items = list(dupes.values())
