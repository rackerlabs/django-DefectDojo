import json

from dojo.models import Finding


class GitlabAPIFuzzingParser(object):
    """
    GitLab API Fuzzing Report

    Ref: https://gitlab.com/gitlab-org/security-products/security-report-schemas/-/blob/master/dist/coverage-fuzzing-report-format.json
    """

    def get_scan_types(self):
        return ["GitLab API Fuzzing Scan"]

    def get_label_for_scan_types(self, scan_type):
        return "GitLab API Fuzzing Scan"

    def get_description_for_scan_types(self, scan_type):
        return "GitLab API Fuzzing scanning report file can be imported in JSON format (option --json)."

    def get_findings(self, file, test):
        findings = []
        data = json.load(file)
        vulnerabilities = data["vulnerabilities"]
        for vulnerability in vulnerabilities:
            title = vulnerability["name"]
            severity = self.normalise_severity(vulnerability["severity"])
            description = vulnerability["category"]
            try:
                location = vulnerability["location"]
                description += "\n" + location["crash_type"]
                description += "\n" + location["crash_state"]
            except:
                pass
            findings.append(
                Finding(
                    title=title,
                    test=test,
                    description=description,
                    severity=severity,
                    static_finding=False,
                    dynamic_finding=True,
                    unique_id_from_tool=vulnerability["id"],
                )
            )
        return findings

    def normalise_severity(self, severity):
        """
        Normalise GitLab's severity to DefectDojo's
        (Critical, High, Medium, Low, Unknown, Info) -> (Critical, High, Medium, Low, Info)
        """
        if severity == "Unknown":
            return "Info"
        return severity
