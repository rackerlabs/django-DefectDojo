__author__ = "Hasan Tayyar Besik"

# Cloned form aws_scout2 scanner
import json
from datetime import datetime

from django.utils.html import strip_tags
from django.utils.text import Truncator

from dojo.models import Finding


class ScoutSuiteParser(object):
    """"ScoutSuite Wiki: https://github.com/nccgroup/ScoutSuite/wiki"""

    item_data = ""
    pdepth = 0

    def get_findings(self, filename, test):
        with open(filename.temporary_file_path(), "r") as fileobj:
            raw_data = fileobj.read()
            raw_data = raw_data.replace("scoutsuite_results =", "")
        data = json.loads(raw_data)
        find_date = datetime.now()
        dupes = {}

        test_description = ""
        account_id = data["account_id"]
        test_description = "%s  **Account:** %s\n" % (test_description, account_id)
        last_run = data["last_run"]
        test_description = "%s  **Ruleset:** %s\n" % (
            test_description,
            last_run["ruleset_name"],
        )
        test_description = "%s  **Ruleset Description:** %s\n" % (
            test_description,
            last_run["ruleset_about"],
        )

        # Summary of Services
        test_description = "%s\n**Services** \n\n" % (test_description)
        for service, items in list(last_run["summary"].items()):
            test_description = "%s\n**%s** \n" % (test_description, service.upper())
            test_description = "%s\n* **Checked Items:** %s\n" % (
                test_description,
                items["checked_items"],
            )
            test_description = "%s* **Flagged Items:** %s\n" % (
                test_description,
                items["flagged_items"],
            )
            test_description = "%s* **Max Level:** %s\n" % (
                test_description,
                items["max_level"],
            )
            test_description = "%s* **Resource Count:** %s\n" % (
                test_description,
                items["resources_count"],
            )
            test_description = "%s* **Rules Count:** %s\n\n" % (
                test_description,
                items["rules_count"],
            )
        test.description = test_description

        scoutsuite_findings = []

        # Configured Services
        for service in list(data["services"].items()):
            for service_item in service:
                if "findings" in service_item:
                    for name, finding in list(service_item["findings"].items()):
                        if finding["items"]:
                            description_text = ""
                            for name in finding["items"]:
                                description_text = (
                                    description_text
                                    + "**Location:** "
                                    + name
                                    + "\n\n---\n"
                                )
                                description_text = description_text + "\n"
                                key = name.split(".")
                                i = 1
                                lookup = service_item
                                while i < len(key):
                                    if key[i] in lookup:
                                        if type(lookup[key[i]]) is dict:
                                            lookup = lookup[key[i]]
                                            if (
                                                key[i - 1] == "security_groups"
                                                or key[i - 1] == "PolicyDocument"
                                            ):
                                                break
                                    i = i + 1

                                self.recursive_print(lookup)
                                description_text = description_text + self.item_data
                                self.item_data = ""

                            refs = finding["references"]
                            mobsf_item = {
                                "category": "Mobile Permissions",
                                "title": finding["description"],
                                "severity": finding["level"],
                                "description": description_text,
                                "references": " ".join(
                                    filter(None, refs)
                                    if hasattr(refs, "__len__")
                                    else []
                                ),
                            }
                            scoutsuite_findings.append(mobsf_item)

        for scoutsuite_finding in scoutsuite_findings:
            title = strip_tags(scoutsuite_finding["title"])
            sev = self.getCriticalityRating(scoutsuite_finding["severity"])
            description = scoutsuite_finding["description"]
            references = scoutsuite_finding["references"]
            dupe_key = sev + title
            if dupe_key in dupes:
                find = dupes[dupe_key]
                if description is not None:
                    find.description += description
            else:
                find = Finding(
                    title=Truncator(title).words(6),
                    cwe=1032,  # Security Configuration Weaknesses, would like to fine tune
                    test=test,
                    active=False,
                    verified=False,
                    description="**Account:** " + account_id + "\n" + description,
                    severity=sev,
                    numerical_severity=Finding.get_numerical_severity(sev),
                    references=references,
                    date=find_date,
                    dynamic_finding=True,
                )
                dupes[dupe_key] = find
        return list(dupes.values())

    def formatview(self, depth):
        if depth > 1:
            return "* "
        else:
            return ""

    def recursive_print(self, src, depth=0, key=""):
        tabs = lambda n: " " * n * 2
        if isinstance(src, dict):
            for key, value in src.items():
                if isinstance(src, str):
                    self.item_data = self.item_data + key + "\n"
                self.recursive_print(value, depth + 1, key)
        elif isinstance(src, list):
            for litem in src:
                self.recursive_print(litem, depth + 2)
        else:
            if self.pdepth != depth:
                self.item_data = self.item_data + "\n"
            if key:
                self.item_data = (
                    self.item_data
                    + self.formatview(depth)
                    + "**%s:** %s\n\n" % (key.title(), src)
                )
            else:
                self.item_data = self.item_data + self.formatview(depth) + "%s\n" % src
            self.pdepth = depth

    # Criticality rating
    def getCriticalityRating(self, rating):
        criticality = "Info"
        if rating == "warning":
            criticality = "Medium"
        elif rating == "danger":
            criticality = "Critical"

        return criticality
