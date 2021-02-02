__author__ = "jaguasch"

import json
from datetime import datetime

from dojo.models import Finding


class AnchoreEngineScanParser(object):
    def get_findings(self, filename, test):
        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)
        dupes = dict()
        find_date = datetime.now()

        for item in data["vulnerabilities"]:
            categories = ""
            language = ""
            mitigation = ""
            impact = ""
            references = ""
            findingdetail = ""
            title = ""
            group = ""
            status = ""
            cve = None

            title = (
                item["vuln"]
                + " - "
                + item["package"]
                + "("
                + item["package_type"]
                + ")"
            )

            if item["vuln"]:
                cve = item["vuln"]

            # Finding details information
            findingdetail += "Image hash: " + data["imageDigest"] + "\n\n"
            findingdetail += "Package: " + item["package"] + "\n\n"
            findingdetail += "Package path: " + item["package_path"] + "\n\n"
            findingdetail += "Package type: " + item["package_type"] + "\n\n"
            findingdetail += "Feed: " + item["feed"] + "/" + item["feed_group"] + "\n\n"
            findingdetail += "CVE: " + item["vuln"] + "\n\n"
            findingdetail += "CPE: " + item["package_cpe"] + "\n\n"

            sev = item["severity"]
            if sev == "Negligible" or sev == "Unknown":
                sev = "Info"

            mitigation += (
                "Upgrade to " + item["package_name"] + " " + item["fix"] + "\n"
            )
            mitigation += "URL: " + item["url"] + "\n"

            references = item["url"]

            dupe_key = (
                data["imageDigest"]
                + "|"
                + item["feed"]
                + "|"
                + item["feed_group"]
                + "|"
                + item["package_name"]
                + "|"
                + item["package_version"]
                + "|"
                + "|"
                + item["package_path"]
                + "|"
                + item["vuln"]
            )

            if dupe_key in dupes:
                find = dupes[dupe_key]
            else:
                dupes[dupe_key] = True

                find = Finding(
                    title=title,
                    test=test,
                    cve=cve,
                    description=findingdetail,
                    severity=sev,
                    numerical_severity=Finding.get_numerical_severity(sev),
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    file_path=item["package_path"],
                    component_name=item["package_name"],
                    component_version=item["package_version"],
                    url=item["url"],
                    date=find_date,
                    static_finding=True,
                    dynamic_finding=False,
                )

                dupes[dupe_key] = find

        return list(dupes.values())
