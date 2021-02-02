__author__ = "jaguasch"

import hashlib
from datetime import datetime

from dojo.models import Finding


class BundlerAuditParser(object):
    def get_findings(self, filename, test):
        if filename is None:
            return ()

        lines = filename.read().decode("utf8")
        dupes = dict()
        find_date = datetime.now()
        warnings = lines.split("\n\n")

        for warning in warnings:
            if not warning.startswith("Name"):
                continue

            gem_report_fields = warning.split("\n")
            for field in gem_report_fields:
                if field.startswith("Name"):
                    gem_name = field.replace("Name: ", "")
                elif field.startswith("Version"):
                    gem_version = field.replace("Version: ", "")
                elif field.startswith("Advisory"):
                    advisory_cve = field.replace("Advisory: ", "")
                elif field.startswith("Criticality"):
                    criticality = field.replace("Criticality: ", "")
                    if criticality.lower() == "unknown":
                        sev = "Medium"
                    else:
                        sev = criticality
                elif field.startswith("URL"):
                    advisory_url = field.replace("URL: ", "")
                elif field.startswith("Title"):
                    advisory_title = field.replace("Title: ", "")
                elif field.startswith("Solution"):
                    advisory_solution = field.replace("Solution: ", "")

            title = (
                "Gem " + gem_name + ": " + advisory_title + " [" + advisory_cve + "]"
            )
            findingdetail = "Gem **" + gem_name + "** has known security issues:\n"
            findingdetail += "**Name**: " + gem_name + "\n"
            findingdetail += "**Version**: " + gem_version + "\n"
            findingdetail += "**Advisory**: " + advisory_cve + "\n"
            mitigation = advisory_solution
            references = advisory_url
            fingerprint = "bundler-audit" + gem_name + gem_version + advisory_cve + sev
            dupe_key = hashlib.md5(fingerprint.encode("utf-8")).hexdigest()
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
                    severity=sev,
                    numerical_severity=Finding.get_numerical_severity(sev),
                    mitigation=mitigation,
                    references=references,
                    url="N/A",
                    date=find_date,
                    static_finding=True,
                )

                dupes[dupe_key] = find

        return list(dupes.values())
