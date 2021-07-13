import json
from dojo.models import Finding


class GitlabSecretDetectionReportParser(object):
    """
    GitLab's secret detection report
    See more: https://gitlab.com/gitlab-org/security-products/security-report-schemas/-/blob/master/dist/secret-detection-report-format.json
    """

    def get_scan_types(self):
        return ["GitLab Secret Detection Report"]

    def get_label_for_scan_types(self, scan_type):
        return "GitLab Secret Detection Report"

    def get_description_for_scan_types(self, scan_type):
        return "GitLab Secret Detection Report file can be imported in JSON format (option --json)."

    def get_findings(self, file, test):
        # Load JSON data from uploaded file
        data = json.load(file)

        findings = []

        # This is required by schema - it won't be null / undefined
        date = data["scan"]["end_time"]

        # Vulnerabilities is stored on vulnerabilities key
        vulnerabilities = data["vulnerabilities"]
        for vulnerability in vulnerabilities:
            title = vulnerability["message"]
            description = vulnerability["description"]
            severity = self.normalise_severity(vulnerability["severity"])
            location = vulnerability["location"]
            finding = Finding(
                test=test,
                title=title,
                description=description,
                date=date,
                severity=severity,
                static_finding=True,
                dynamic_finding=False,
                unique_id_from_tool=vulnerability["id"],
            )

            if "file" in location:
                finding.file_path = location["file"]
            if "start_line" in location:
                finding.line = int(location["start_line"])
            if "raw_source_code_extract" in vulnerability:
                finding.description += "\n" + vulnerability["raw_source_code_extract"]

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
