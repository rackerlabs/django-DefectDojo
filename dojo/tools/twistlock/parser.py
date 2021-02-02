import csv
import hashlib
import io
import json
import logging
import textwrap

from dojo.models import Finding

logger = logging.getLogger(__name__)


class TwistlockCSVParser(object):
    def parse_issue(self, row, test):
        if not row:
            return None

        data_vulnerability_id = row.get("CVE ID", "")
        data_package_version = row.get("Package Version", "")
        data_fix_status = row.get("Fix Status", "")
        data_package_name = row.get("Packages", "")
        data_id = row.get("Id", "")
        data_severity = row.get("Severity", "")
        data_cvss = row.get("CVSS", "")
        data_description = description_column = row.get("Description", "")

        if data_vulnerability_id and data_package_name:
            title = (
                data_vulnerability_id
                + ": "
                + data_package_name
                + " - "
                + data_package_version
            )
        elif data_package_name and data_package_version:
            title = data_package_name + " - " + data_package_version
        else:
            title = data_description

        finding = Finding(
            title=textwrap.shorten(title, width=255, placeholder="..."),
            cve=data_vulnerability_id,
            test=test,
            severity=convert_severity(data_severity),
            description=data_description
            + "<p> Vulnerable Package: "
            + data_package_name
            + "</p><p> Current Version: "
            + str(data_package_version)
            + "</p>",
            mitigation=data_fix_status,
            component_name=textwrap.shorten(
                data_package_name, width=200, placeholder="..."
            ),
            component_version=data_package_version,
            active=False,
            verified=False,
            false_p=False,
            duplicate=False,
            out_of_scope=False,
            mitigated=None,
            severity_justification="(CVSS v3 base score: {})".format(data_cvss),
            impact=data_severity,
        )

        finding.description = finding.description.strip()

        return finding

    def parse(self, filename, test):
        if filename is None:
            self.items = ()
            return
        content = filename.read()
        dupes = dict()
        if type(content) is bytes:
            content = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter=",", quotechar='"')
        for row in reader:
            finding = self.parse_issue(row, test)
            if finding is not None:
                key = hashlib.md5(
                    (
                        finding.severity
                        + "|"
                        + finding.title
                        + "|"
                        + finding.description
                    ).encode("utf-8")
                ).hexdigest()
                if key not in dupes:
                    dupes[key] = finding
        return list(dupes.values())


class TwistlockJsonParser(object):
    def parse(self, json_output, test):
        tree = self.parse_json(json_output)
        items = []
        if tree:
            items = [data for data in self.get_items(tree, test)]
        return items

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
        if "results" in tree:
            try:
                vulnerabilityTree = tree["results"][0]["vulnerabilities"]

                for node in vulnerabilityTree:

                    item = get_item(node, test)
                    unique_key = node["id"] + str(
                        node["packageName"]
                        + str(node["packageVersion"])
                        + str(node["severity"])
                    )
                    items[unique_key] = item
            except KeyError as ke:
                logger.warn("Could not find key {}".format(ke))

        return list(items.values())


def get_item(vulnerability, test):
    severity = (
        convert_severity(vulnerability["severity"])
        if "severity" in vulnerability
        else "Info"
    )
    vector = (
        vulnerability["vector"]
        if "vector" in vulnerability
        else "CVSS vector not provided. "
    )
    status = (
        vulnerability["status"]
        if "status" in vulnerability
        else "There seems to be no fix yet. Please check description field."
    )
    cvss = vulnerability["cvss"] if "cvss" in vulnerability else "No CVSS score yet."
    riskFactors = (
        vulnerability["riskFactors"]
        if "riskFactors" in vulnerability
        else "No risk factors."
    )

    # create the finding object
    finding = Finding(
        title=vulnerability["id"]
        + ": "
        + vulnerability["packageName"]
        + " - "
        + vulnerability["packageVersion"],
        cve=vulnerability["id"],
        test=test,
        severity=severity,
        description=vulnerability["description"]
        + "<p> Vulnerable Package: "
        + vulnerability["packageName"]
        + "</p><p> Current Version: "
        + str(vulnerability["packageVersion"])
        + "</p>",
        mitigation=status.title(),
        references=vulnerability["link"],
        component_name=vulnerability["packageName"],
        component_version=vulnerability["packageVersion"],
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        severity_justification="{} (CVSS v3 base score: {})\n\n{}".format(
            vector, cvss, riskFactors
        ),
        impact=severity,
    )

    finding.description = finding.description.strip()

    return finding


def convert_severity(severity):
    if severity.lower() == "important":
        return "High"
    elif severity.lower() == "moderate":
        return "Medium"
    elif severity.lower() == "information":
        return "Info"
    elif severity.lower() == "informational":
        return "Info"
    elif severity == "":
        return "Info"
    else:
        return severity.title()


class TwistlockParser(object):
    def get_findings(self, filename, test):

        if filename is None:
            return list()

        if filename.name.lower().endswith(".json"):
            return TwistlockJsonParser().parse(filename, test)
        elif filename.name.lower().endswith(".csv"):
            return TwistlockCSVParser().parse(filename, test)
        else:
            raise Exception("Unknown File Format")
