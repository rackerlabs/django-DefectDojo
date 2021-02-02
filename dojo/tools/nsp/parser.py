import json

from dojo.models import Finding


class NspParser(object):
    def get_findings(self, json_output, test):

        tree = self.parse_json(json_output)

        if tree:
            self.items = [data for data in self.get_items(tree, test)]
        else:
            self.items = []

    def parse_json(self, json_output):
        try:
            data = json_output.read()
            try:
                tree = json.loads(str(data, "utf-8"))
            except:
                tree = json.loads(data)
        except:
            raise Exception("Invalid format")

        return tree

    def get_items(self, tree, test):
        items = {}

        for node in tree:
            item = get_item(node, test)
            unique_key = node["title"] + str(node["path"])
            items[unique_key] = item

        return list(items.values())


def get_item(item_node, test):

    # Following the CVSS Scoring per https://nvd.nist.gov/vuln-metrics/cvss

    if item_node["cvss_score"] <= 3.9:
        severity = "Low"
    elif item_node["cvss_score"] > 4.0 and item_node["cvss_score"] <= 6.9:
        severity = "Medium"
    elif item_node["cvss_score"] > 7.0 and item_node["cvss_score"] <= 8.9:
        severity = "High"
    else:
        severity = "Critical"

    finding = Finding(
        title=item_node["title"]
        + " - "
        + "("
        + item_node["module"]
        + ", "
        + item_node["version"]
        + ")",
        test=test,
        severity=severity,
        description=item_node["overview"]
        + "\n Vulnerable Module: "
        + item_node["module"]
        + "\n Vulnerable Versions: "
        + str(item_node["vulnerable_versions"])
        + "\n Current Version: "
        + str(item_node["version"])
        + "\n Patched Version: "
        + str(item_node["patched_versions"])
        + "\n Vulnerable Path: "
        + " > ".join(item_node["path"])
        + "\n CVSS Score: "
        + str(item_node["cvss_score"])
        + "\n CVSS Vector: "
        + str(item_node["cvss_vector"]),
        mitigation=item_node["recommendation"],
        references=item_node["advisory"],
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        impact="No impact provided",
    )

    return finding
