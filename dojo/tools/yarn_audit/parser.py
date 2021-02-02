import jsonlines

from dojo.models import Finding


class YarnAuditParser(object):
    def get_findings(self, json_output, test):

        tree = self.parse_json(json_output)

        if tree:
            return [data for data in self.get_items(tree, test)]
        else:
            return []

    def parse_json(self, json_output):
        if json_output is None:
            return None
        try:
            data = []
            reader = jsonlines.Reader(json_output)
            for obj in reader:
                data.append(obj)
        except:
            raise Exception("Invalid format")
        return data

    def get_items(self, tree, test):
        items = {}
        for element in tree:
            if element.get("type") == "auditAdvisory":
                node = element.get("data").get("advisory")
                item = get_item(node, test)
                unique_key = str(node.get("id")) + str(node.get("module_name"))
                items[unique_key] = item
            elif element.get("type") == "error":
                error = element.get("data")
                raise ValueError("yarn audit report contains errors: %s", error)

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
    for finding in item_node["findings"]:
        paths += (
            "\n  - "
            + str(finding["version"])
            + ":"
            + str(",".join(finding["paths"][:25]))
        )
        if len(finding["paths"]) > 25:
            paths += "\n  - ..... (list of paths truncated after 25 paths)"

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
        cwe=item_node["cwe"][4:],
        cve=item_node["cves"][0] if (len(item_node["cves"]) > 0) else None,
        mitigation=item_node["recommendation"],
        references=item_node["url"],
        component_name=item_node["module_name"],
        component_version=item_node["findings"][0]["version"],
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
