import hashlib
import json

from dojo.models import Finding


class CCVSReportParser(object):
    """
    Read JSON data from CCVS compatible format and import it to DefectDojo
    """

    def get_findings(self, json_output, test):

        if json_output is None:
            return list()

        tree = self.parse_json(json_output)
        if tree:
            return [data for data in self.get_items(tree, test)]
        else:
            return list()

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

        for vendor in tree.get("ccvs_results", {}):
            vendor_results = tree["ccvs_results"][vendor]
            for severity in vendor_results:
                for vuln in vendor_results[severity]:
                    vuln["vendor"] = vendor
                    vuln["image_id"] = tree["vendors"][vendor]["image_id"]
                    unique_key = hashlib.md5(str(vuln).encode("utf-8")).hexdigest()
                    item = get_item(vuln, test)
                    items[unique_key] = item

        return list(items.values())


def get_item(item_node, test):
    if item_node["severity"] in ["Negligible", "Unknown"]:
        item_node["severity"] = "Info"

    description = "Package: " + item_node["package_name"] + "\n"
    description += "Version: " + item_node["package_version"] + "\n"
    description += "Vendor: " + item_node["vendor"]
    mitigation = (
        "Upgrade to " + item_node["package_name"] + " " + str(item_node["fix"]) + "\n"
    )
    references = "URL: " + item_node["url"] + "\n"
    title = item_node["name"] + " - " + item_node["package_name"]

    finding = Finding(
        title=title,
        test=test,
        severity=item_node["severity"],
        description=description,
        mitigation=mitigation,
        references=references,
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        component_name=item_node["package_name"],
        component_version=item_node["package_version"],
        static_finding=True,
        dynamic_finding=False,
        impact="No impact provided",
    )

    return finding
