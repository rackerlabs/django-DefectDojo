__author__ = "aaronweaver"

import json
import logging
from datetime import datetime

from dojo.models import Finding


class BanditParser(object):
    def get_findings(self, filename, test):

        if filename is None:
            return

        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)

        dupes = dict()
        if "generated_at" in data:
            find_date = datetime.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ")

        for item in data["results"]:
            categories = ""
            language = ""
            mitigation = ""
            impact = ""
            references = ""
            findingdetail = ""
            title = ""
            group = ""
            status = ""

            title = "Test Name: " + item["test_name"] + " Test ID: " + item["test_id"]

            #  ##### Finding details information ######
            findingdetail += "Filename: " + item["filename"] + "\n"
            findingdetail += "Line number: " + str(item["line_number"]) + "\n"
            findingdetail += "Issue Confidence: " + item["issue_confidence"] + "\n\n"
            findingdetail += "Code:\n"
            findingdetail += item["code"] + "\n"

            sev = item["issue_severity"]
            mitigation = item["issue_text"]
            references = item["test_id"]

            dupe_key = title + item["filename"] + str(item["line_number"])

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
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    file_path=item["filename"],
                    line=item["line_number"],
                    url="N/A",
                    date=find_date,
                    static_finding=True,
                )
                logging.debug(f"Bandit parser {find}")
                dupes[dupe_key] = find
                findingdetail = ""

        return list(dupes.values())
