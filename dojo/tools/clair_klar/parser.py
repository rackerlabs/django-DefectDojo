import json
import logging

from dojo.models import Finding

logger = logging.getLogger(__name__)


class ClairKlarParser(object):
    def get_findings(self, json_output, test):

        tree = self.parse_json(json_output)

        items = list()
        clair_severities = [
            "Unknown",
            "Negligible",
            "Low",
            "Medium",
            "High",
            "Critical",
            "Defcon1",
        ]
        if tree:
            for clair_severity in clair_severities:
                items.extend(self.set_items_for_severity(tree, test, clair_severity))
        return items

    def parse_json(self, json_output):
        try:
            data = json_output.read()
            try:
                tree = json.loads(str(data, "utf-8"))
            except:
                tree = json.loads(data)
            subtree = tree.get("Vulnerabilities")
        except:
            raise Exception("Invalid format")

        return subtree

    def set_items_for_severity(self, tree, test, severity):
        items = list()
        tree_severity = tree.get(severity)
        if tree_severity:
            for data in self.get_items(tree_severity, test):
                items.append(data)
            logger.info("Appended findings for severity " + severity)
        else:
            logger.info("No findings for severity " + severity)
        return items

    def get_items(self, tree_severity, test):
        items = {}

        for node in tree_severity:
            item = get_item(node, test)
            unique_key = str(node["Name"]) + str(node["FeatureName"])
            items[unique_key] = item

        return items.values()


def get_item(item_node, test):
    if item_node["Severity"] == "Negligible":
        severity = "Info"
    elif item_node["Severity"] == "Unknown":
        severity = "Critical"
    elif item_node["Severity"] == "Defcon1":
        severity = "Critical"
    else:
        severity = item_node["Severity"]
    description = ""
    if "Description" in item_node:
        description += item_node["Description"] + "\n<br /> "
    if "FeatureName" in item_node:
        description += "Vulnerable feature: " + item_node["FeatureName"] + "\n<br />"
    if "FeatureVersion" in item_node:
        description += " Vulnerable Versions: " + str(item_node["FeatureVersion"])

    mitigation = ""
    if "FixedBy" in item_node:
        description = description + "\n Fixed by: " + str(item_node["FixedBy"])
        mitigation = (
            "Please use version "
            + item_node["FixedBy"]
            + " of library "
            + item_node["FeatureName"]
        )
    else:
        mitigation = "A patch could not been found"

    link = ""
    if "Link" in item_node:
        link = item_node["Link"]

    finding = Finding(
        title=item_node["Name"]
        + " - "
        + "("
        + item_node["FeatureName"]
        + ", "
        + item_node["FeatureVersion"]
        + ")",
        test=test,
        severity=severity,
        description=description,
        mitigation=mitigation,
        references=link,
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        cwe=1035,  # Vulnerable Third Party Component
        static_finding=True,
        dynamic_finding=False,
        impact="No impact provided",
    )

    return finding
