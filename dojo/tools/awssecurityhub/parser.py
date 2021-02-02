import json
from datetime import datetime

from dojo.models import Finding


class AwsSecurityFindingFormatParser:
    def get_findings(self, filehandle, test):
        tree = json.load(filehandle)
        return self.get_items(tree, test)

    def get_items(self, tree, test):
        items = {}
        # DefectDojo/django-DefectDojo/issues/2780
        findings = tree.get("Findings", tree.get("findings", None))

        if not findings:
            return list()

        for node in findings:
            item = get_item(node, test)
            key = node["Id"]
            items[key] = item

        return list(items.values())


def get_item(finding, test):
    title = finding.get("Title", "")
    severity = finding.get("Severity", {}).get("Label", "INFORMATIONAL").title()
    description = finding.get("Description", "")
    mitigation = (
        finding.get("Remediation", {}).get("Recommendation", {}).get("Text", "")
    )
    references = finding.get("Remediation", {}).get("Recommendation", {}).get("Url")
    cve = None
    cwe = None
    active = False
    verified = False
    false_p = False
    duplicate = False
    out_of_scope = False
    impact = None

    if finding.get("Compliance", {}).get("Status", "PASSED"):
        if finding.get("LastObservedAt", None):
            try:
                mitigated = datetime.strptime(
                    finding.get("LastObservedAt"), "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except:
                mitigated = datetime.strptime(
                    finding.get("LastObservedAt"), "%Y-%m-%dT%H:%M:%fZ"
                )
        else:
            mitigated = datetime.utcnow()
    else:
        mitigated = None

    finding = Finding(
        title=title,
        test=test,
        severity=severity,
        description=description,
        mitigation=mitigation,
        references=references,
        cve=cve,
        cwe=cwe,
        active=active,
        verified=verified,
        false_p=false_p,
        duplicate=duplicate,
        out_of_scope=out_of_scope,
        mitigated=mitigated,
        impact="No impact provided",
    )

    return finding
