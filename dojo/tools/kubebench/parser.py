import json

from dojo.models import Finding


class KubeBenchParser(object):
    def get_findings(self, json_output, test):
        tree = self.parse_json(json_output)
        return self.get_chapters(tree, test)

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

    def get_chapters(self, tree, test):
        items = []

        for node in tree:
            items_from_tests = get_tests(node, test)
            items += items_from_tests

        return list(items)


def get_tests(tree, test):
    items_from_tests = []

    description = ""
    if "id" in tree:
        description += tree["id"] + " "
    if "text" in tree:
        description += tree["text"]
    description += "\n"

    for node in tree["tests"]:
        items_from_results = get_results(node, test, description)
        items_from_tests += items_from_results

    return list(items_from_tests)


def get_results(tree, test, description):
    items_from_results = []

    if "section" in tree:
        description += tree["section"] + " "
    if "desc" in tree:
        description += tree["desc"]
    description += "\n"

    for node in tree["results"]:
        item = get_item(node, test, description)
        if item:
            items_from_results.append(item)

    return list(items_from_results)


def get_item(vuln, test, description):

    if ("status" in vuln) and (vuln["status"].upper() != "FAIL"):
        return None

    if "test_number" not in vuln:
        return None

    unique_id_from_tool = vuln["test_number"]

    title = ""
    if "test_desc" in vuln:
        title = vuln["test_desc"]
    else:
        title = "test_desc not found"

    if "test_number" in vuln:
        description += vuln["test_number"] + " "
    if "test_desc" in vuln:
        description += vuln["test_desc"]
    description += "\n"
    if "audit" in vuln:
        description += "Audit: {}\n".format(vuln["audit"])

    # kube-bench doesn't define severities. Sine the findings are
    # vulnerabilities, we set them to Medium
    severity = "Medium"
    numerical_severity = Finding.get_numerical_severity(severity)

    mitigation = ""
    if "remediation" in vuln:
        mitigation = vuln["remediation"]

    finding = Finding(
        title=title,
        test=test,
        active=False,
        verified=False,
        description=description,
        severity=severity,
        numerical_severity=numerical_severity,
        mitigation=mitigation,
        unique_id_from_tool=unique_id_from_tool,
        static_finding=True,
        dynamic_finding=False,
    )

    return finding
