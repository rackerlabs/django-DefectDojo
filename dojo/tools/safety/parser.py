import json
import logging
import urllib

from dojo.models import Finding

logger = logging.getLogger(__name__)


class SafetyParser(object):
    def get_findings(self, json_output, test):

        # Grab Safety DB for CVE lookup
        url = "https://raw.githubusercontent.com/pyupio/safety-db/master/data/insecure_full.json"
        try:
            response = urllib.request.urlopen(url)
            safety_db = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.warn("Error Message: %s", e)
            logger.warn(
                "Could not resolve %s. Fallback is using the offline version from dojo/tools/safety/insecure_full.json.",
                url,
            )
            with open("dojo/tools/safety/insecure_full.json", "r") as f:
                safety_db = json.load(f)
            f.close()

        tree = self.parse_json(json_output)
        return self.get_items(tree, test, safety_db)

    def parse_json(self, json_output):
        data = json_output.read() or "[]"
        try:
            json_obj = json.loads(str(data, "utf-8"))
        except:
            json_obj = json.loads(data)
        tree = {
            l[4]: {
                "package": str(l[0]),
                "affected": str(l[1]),
                "installed": str(l[2]),
                "description": str(l[3]),
                "id": str(l[4]),
            }
            for l in json_obj
        }  # noqa: E741
        return tree

    def get_items(self, tree, test, safety_db):
        items = {}

        for key, node in tree.items():
            item = get_item(node, test, safety_db)
            items[key] = item

        return list(items.values())


def get_item(item_node, test, safety_db):
    severity = "Info"  # Because Safety doesn't include severity rating
    cve = (
        "".join(
            a["cve"] or ""
            for a in safety_db[item_node["package"]]
            if a["id"] == "pyup.io-" + item_node["id"]
        )
        or None
    )
    title = item_node["package"] + " (" + item_node["affected"] + ")"

    finding = Finding(
        title=title + " | " + cve if cve else title,
        test=test,
        severity=severity,
        description=item_node["description"]
        + "\n Vulnerable Package: "
        + item_node["package"]
        + "\n Installed Version: "
        + item_node["installed"]
        + "\n Vulnerable Versions: "
        + item_node["affected"]
        + "\n CVE: "
        + (cve or "N/A")
        + "\n ID: "
        + item_node["id"],
        cve=cve,
        cwe=1035,  # Vulnerable Third Party Component
        mitigation="No mitigation provided",
        references="No reference provided",
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        impact="No impact provided",
    )

    return finding
