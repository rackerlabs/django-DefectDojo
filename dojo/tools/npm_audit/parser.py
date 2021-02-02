import json
import logging
import re

from dojo.models import Finding

logger = logging.getLogger(__name__)


class NpmAuditParser(object):
    def get_findings(self, json_output, test):
        tree = self.parse_json(json_output)
        return self.get_items(tree, test)

    def parse_json(self, json_output):
        if json_output is None:
            self.items = []
            return
        try:
            data = json_output.read()
            try:
                tree = json.loads(str(data, "utf-8"))
            except:
                tree = json.loads(data)
        except:
            raise Exception("Invalid format, unable to parse json.")

        if tree.get("auditReportVersion"):
            raise ValueError(
                "npm7 with auditReportVersion 2 or higher not yet supported as it lacks the most important fields in the reports"
            )

        if tree.get("error"):
            error = tree.get("error")
            code = error["code"]
            summary = error["summary"]
            raise ValueError("npm audit report contains errors: %s, %s", code, summary)

        subtree = tree.get("advisories")

        return subtree

    def get_items(self, tree, test):
        items = {}

        for key, node in tree.items():
            item = get_item(node, test)
            unique_key = str(node["id"]) + str(node["module_name"])
            items[unique_key] = item

        return list(items.values())


def get_item(item_node, test):

    if item_node["severity"] == "low":
        severity = "Low"
    elif item_node["severity"] == "moderate":
        severity = "Medium"
    elif item_node["severity"] == "high":
        severity = "High"
    elif item_node["severity"] == "critical":
        severity = "Critical"
    else:
        severity = "Info"

    paths = ""
    component_version = None
    for npm_finding in item_node["findings"]:
        # use first version as component_version
        component_version = (
            npm_finding["version"] if not component_version else component_version
        )
        paths += (
            "\n  - "
            + str(npm_finding["version"])
            + ":"
            + str(",".join(npm_finding["paths"][:25]))
        )
        if len(npm_finding["paths"]) > 25:
            paths += "\n  - ..... (list of paths truncated after 25 paths)"

    # Use CWE-1035 as fallback
    cwe = 1035  # Vulnerable Third Party Component
    if item_node["cwe"]:
        m = re.match(r"^(CWE-)?(\d+)", item_node["cwe"])
        if m:
            cwe = int(m.group(2))

    dojo_finding = Finding(
        title=item_node["title"]
        + " - "
        + "("
        + item_node["module_name"]
        + ", "
        + item_node["vulnerable_versions"]
        + ")",
        test=test,
        severity=severity,
        file_path=item_node["findings"][0]["paths"][0],
        description=item_node["url"]
        + "\n"
        + item_node["overview"]
        + "\n Vulnerable Module: "
        + item_node["module_name"]
        + "\n Vulnerable Versions: "
        + str(item_node["vulnerable_versions"])
        + "\n Patched Version: "
        + str(item_node["patched_versions"])
        + "\n Vulnerable Paths: "
        + str(paths)
        + "\n CWE: "
        + str(item_node["cwe"])
        + "\n Access: "
        + str(item_node["access"]),
        cwe=cwe,
        cve=item_node["cves"][0] if (len(item_node["cves"]) > 0) else None,
        mitigation=item_node["recommendation"],
        references=item_node["url"],
        component_name=item_node["module_name"],
        component_version=component_version,
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        impact="No impact provided",
        static_finding=True,
        dynamic_finding=False,
    )

    return dojo_finding
