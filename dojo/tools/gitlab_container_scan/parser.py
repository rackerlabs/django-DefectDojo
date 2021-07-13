import json
import textwrap
from datetime import datetime
from dojo.models import Finding


class GitlabContainerScanParser(object):
    """
    GitLab's container scanning report
    See more: https://gitlab.com/gitlab-org/security-products/security-report-schemas/-/blob/master/dist/container-scanning-report-format.json
    """

    def get_scan_types(self):
        return ["GitLab Container Scan"]

    def get_label_for_scan_types(self, scan_type):
        return "GitLab Container Scan"

    def get_description_for_scan_types(self, scan_type):
        return "GitLab Container Scanning report file can be imported in JSON format (option --json)."

    def get_findings(self, file, test):

        findings = []

        # Load JSON data from uploaded file
        data = json.load(file)

        # This is required by schema - it won't be null / undefined
        date = datetime.strptime(data["scan"]["end_time"], "%Y-%m-%dT%H:%M:%S")

        # Vulnerabilities is stored on vulnerabilities key
        vulnerabilities = data["vulnerabilities"]
        for vulnerability in vulnerabilities:
            title = vulnerability["message"]
            description = vulnerability["description"]
            severity = self.normalise_severity(vulnerability["severity"])
            dependency = vulnerability["location"]["dependency"]
            finding = Finding(
                title=title,
                date=date,
                test=test,
                description=description,
                severity=severity,
                static_finding=True,
                dynamic_finding=False,
                unique_id_from_tool=vulnerability["id"],
            )

            # Add component fields if not empty
            for id in vulnerability["identifiers"]:
                if "type" in id:
                    if id.get("type") == "cve":
                        finding.cve = id["value"]
                    if id.get("type") == "cwe":
                        finding.cwe = id["value"]

            # Check package key before name as both is optional on GitLab schema
            if "package" in dependency:
                if "name" in dependency["package"]:
                    finding.component_name = textwrap.shorten(
                        dependency["package"]["name"], width=190, placeholder="..."
                    )

            if "version" in dependency:
                finding.component_version = textwrap.shorten(
                    dependency["version"], width=90, placeholder="..."
                )

            if "solution" in vulnerability:
                finding.mitigation = vulnerability["solution"]

            findings.append(finding)

        return findings

    def normalise_severity(self, severity):
        """
        Normalise GitLab's severity to DefectDojo's
        (Critical, High, Medium, Low, Unknown, Info) -> (Critical, High, Medium, Low, Info)
        """
        if severity == "Unknown":
            return "Info"
        return severity
