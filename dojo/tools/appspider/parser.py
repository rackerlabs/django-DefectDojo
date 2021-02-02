import urllib.parse
from xml.dom import NamespaceErr

import html2text
from defusedxml import ElementTree

from dojo.models import Endpoint, Finding


class AppSpiderXMLParser(object):
    """Parser for Rapid7 AppSpider reports"""

    def get_findings(self, filename, test):

        if filename is None:
            return

        vscan = ElementTree.parse(filename)
        root = vscan.getroot()

        if "VulnSummary" not in str(root.tag):
            raise NamespaceErr(
                "Please ensure that you are uploading AppSpider's VulnerabilitiesSummary.xml file."
                "At this time it is the only file that is consumable by DefectDojo."
            )

        dupes = dict()

        for finding in root.iter("Vuln"):
            severity = self.convert_severity(finding.find("AttackScore").text)
            title = finding.find("VulnType").text
            description = finding.find("Description").text
            mitigation = finding.find("Recommendation").text
            vuln_url = finding.find("VulnUrl").text

            parts = urllib.parse.urlparse(vuln_url)

            cwe = int(finding.find("CweId").text)

            dupe_key = severity + title
            unsaved_endpoints = list()
            unsaved_req_resp = list()

            if title is None:
                title = ""
            if description is None:
                description = ""
            if mitigation is None:
                mitigation = ""

            if dupe_key in dupes:
                find = dupes[dupe_key]

                unsaved_endpoints.append(find.unsaved_endpoints)
                unsaved_req_resp.append(find.unsaved_req_resp)

            else:
                find = Finding(
                    title=title,
                    test=test,
                    active=False,
                    verified=False,
                    description=html2text.html2text(description),
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation=html2text.html2text(mitigation),
                    impact="N/A",
                    references=None,
                    cwe=cwe,
                )
                find.unsaved_endpoints = unsaved_endpoints
                find.unsaved_req_resp = unsaved_req_resp
                dupes[dupe_key] = find

                for attack in finding.iter("AttackRequest"):
                    req = attack.find("Request").text
                    resp = attack.find("Response").text

                    find.unsaved_req_resp.append({"req": req, "resp": resp})

                find.unsaved_endpoints.append(
                    Endpoint(
                        protocol=parts.scheme,
                        host=parts.netloc,
                        path=parts.path,
                        query=parts.query,
                        fragment=parts.fragment,
                        product=test.engagement.product,
                    )
                )

        return list(dupes.values())

    @staticmethod
    def convert_severity(val):
        severity = "Info"
        if val == "0-Safe":
            severity = "Info"
        elif val == "1-Informational":
            severity = "Low"
        elif val == "2-Low":
            severity = "Medium"
        elif val == "3-Medium":
            severity = "High"
        elif val == "4-High":
            severity = "Critical"
        return severity
