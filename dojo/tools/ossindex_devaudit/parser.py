import json
from json import JSONDecodeError

from dojo.models import Finding


class OssIndexDevauditParser(object):
    """OssIndex Devaudit Results Parser
    Parses files created by the Sonatype OssIndex Devaudit tool
    https://github.com/sonatype-nexus-community/DevAudit
    """

    def get_findings(self, json_file, test):

        tree = self.parse_json(json_file)

        if tree:
            return list([data for data in self.get_items(tree, test)])
        else:
            return list()

    def parse_json(self, json_file):
        if json_file is None:
            return None
        try:
            tree = json.load(json_file)
        except JSONDecodeError:
            raise Exception("Invalid format")

        return tree

    def get_items(self, tree, test):

        items = {}

        results = {key: value for (key, value) in tree.items()}
        for package in results.get("Packages", []):
            package_data = package["Package"]
            if len(package.get("Vulnerabilities", [])) > 0:
                for vulnerability in package.get("Vulnerabilities", []):
                    item = get_item(
                        dependency_name=package_data["name"],
                        dependency_version=package_data["version"],
                        dependency_source=package_data["pm"],
                        vulnerability=vulnerability,
                        test=test,
                    )
                    unique_key = vulnerability["id"]
                    items[unique_key] = item

        return items.values()


def get_item(
    dependency_name, dependency_version, dependency_source, vulnerability, test
):

    cwe_data = vulnerability.get("cwe", "CWE-1035")
    if cwe_data is None or cwe_data.startswith("CWE") is False:
        cwe_data = "CWE-1035"
    try:
        cwe = int(cwe_data.split("-")[1])
    except ValueError:
        raise ValueError("Attempting to convert the CWE value to an integer failed")

    finding = Finding(
        title=dependency_source
        + ":"
        + dependency_name
        + " - "
        + "("
        + dependency_version
        + ", "
        + cwe_data
        + ")",
        test=test,
        severity=get_severity(vulnerability.get("cvssScore", "")),
        description=vulnerability["title"],
        cwe=cwe,
        cvssv3=vulnerability["cvssVector"].replace("CVSS:3.0", ""),
        mitigation="Upgrade the component to the latest non-vulnerable version, or remove the package if it is not in use.",
        references=vulnerability.get("reference", ""),
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        static_finding=False,
        dynamic_finding=False,
        impact="No impact provided by scan",
    )

    return finding


def get_severity(cvss_score):

    result = "Info"

    if cvss_score != "":
        ratings = [
            ("Critical", 9.0, 10.0),
            ("High", 7.0, 8.9),
            ("Medium", 4.0, 6.9),
            ("Low", 0.1, 3.9),
        ]

        for severity, low, high in ratings:
            if low <= float(cvss_score) <= high:
                result = severity

    return result
