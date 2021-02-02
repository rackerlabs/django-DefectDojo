import json

from dojo.models import Finding
from dojo.tools.risk_recon.api import RiskReconAPI


class RiskReconParser(object):
    def get_findings(self, filename, test):
        if filename:
            tree = filename.read()
            try:
                data = json.loads(str(tree, "utf-8"))
            except:
                data = json.loads(tree)

            findings = []
            if not data.get("test", None):
                api = RiskReconAPI(
                    data.get("api_key", None),
                    data.get("url_endpoint", None),
                    data.get("companies", data.get("filters", [])),
                )
                findings = api.findings
            else:
                findings = data.get("findings")

            return self._get_findings_internal(findings, test)

    def _get_findings_internal(self, findings, test):
        dupes = dict()
        for item in findings:
            findingdetail = ""
            title = (
                item.get("vendor")
                + ": "
                + item.get("finding")
                + " - "
                + item.get("domain_name")
                + "("
                + item.get("ip_address")
                + ")"
            )

            # Finding details information
            findingdetail += "**Context:** " + item.get("finding_context") + "\n"
            findingdetail += "**Value:** " + item.get("finding_data_value") + "\n"
            findingdetail += (
                "**Hosting Provider:** " + item.get("hosting_provider") + "\n"
            )
            findingdetail += "**Host Name:** " + item.get("host_name") + "\n"
            findingdetail += (
                "**Security Domain:** " + item.get("security_domain") + "\n"
            )
            findingdetail += (
                "**Security Criteria:** " + item.get("security_criteria") + "\n"
            )
            findingdetail += "**Asset Value:** " + item.get("asset_value") + "\n"
            findingdetail += "**Country:** " + item.get("country_name") + "\n"
            findingdetail += "**Priority:** " + item.get("priority") + "\n"
            findingdetail += "**First Seen:** " + item.get("first_seen") + "\n"

            sev = item.get("severity", "").capitalize()
            sev = "Info" if not sev else sev

            tags = (
                item.get("security_domain")[:20]
                + ", "
                + item.get("security_criteria")[:20]
            )

            dupe_key = title + "|" + tags + "|" + findingdetail

            if dupe_key in dupes:
                find = dupes[dupe_key]
            else:
                dupes[dupe_key] = True

                find = Finding(
                    title=title,
                    test=test,
                    description=findingdetail,
                    severity=sev,
                    mitigation="N/A",
                    impact="N/A",
                    static_finding=False,
                    dynamic_finding=True,
                )

                dupes[dupe_key] = find
                find.unsaved_tags = tags

        return list(dupes.values())
