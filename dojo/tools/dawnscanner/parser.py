__author__ = "jaguasch"

import hashlib
import json
import re

from dateutil import parser

from dojo.models import Finding


class DawnScannerParser(object):
    def get_findings(self, filename, test):
        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)

        dupes = dict()
        find_date = parser.parse(data["scan_started"])

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

            title = item["name"].upper()
            if "CVE" in title:
                # FIXME switch to a function
                cve = re.findall(r"CVE-\d{4}-\d{4,7}", title)[0]
            else:
                cve = None
            # Finding details information
            findingdetail = (
                item["message"]
                if item["message"][0:2] != "b,"
                else item["message"][0:-1]
            )
            sev = item["severity"].capitalize()
            mitigation = item["remediation"]
            references = item["cve_link"]

            dupe_key = hashlib.md5(str(sev + "|" + title).encode("utf-8")).hexdigest()

            if dupe_key in dupes:
                find = dupes[dupe_key]
            else:
                dupes[dupe_key] = True

                find = Finding(
                    title=title,
                    test=test,
                    active=False,
                    cve=cve,
                    verified=False,
                    description=findingdetail,
                    severity=sev,
                    numerical_severity=Finding.get_numerical_severity(sev),
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    url="N/A",
                    date=find_date,
                    static_finding=True,
                )

                dupes[dupe_key] = find
        return list(dupes.values())
