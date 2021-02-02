import json
import logging

from dojo.models import Finding

logger = logging.getLogger(__name__)


class DependencyTrackParser(object):
    """
    A class that can be used to parse the JSON Finding Packaging Format (FPF) export from OWASP Dependency Track.

    See here for more info on this JSON format: https://docs.dependencytrack.org/integrations/file-formats/

    A typical Finding Packaging Format (FPF) export looks like the following:

    {
        "version": "1.0",
        "meta" : {
            "application": "Dependency-Track",
            "version": "3.4.0",
            "timestamp": "2018-11-18T23:31:42Z",
            "baseUrl": "http://dtrack.example.org"
        },
        "project" : {
            "uuid": "ca4f2da9-0fad-4a13-92d7-f627f3168a56",
            "name": "Acme Example",
            "version": "1.0",
            "description": "A sample application"
        },
        "findings" : [
            {
                "component": {
                    "uuid": "b815b581-fec1-4374-a871-68862a8f8d52",
                    "name": "timespan",
                    "version": "2.3.0",
                    "purl": "pkg:npm/timespan@2.3.0"
                },
                "vulnerability": {
                    "uuid": "115b80bb-46c4-41d1-9f10-8a175d4abb46",
                    "source": "NPM",
                    "vulnId": "533",
                    "title": "Regular Expression Denial of Service",
                    "subtitle": "timespan",
                    "severity": "LOW",
                    "severityRank": 3,
                    "cweId": 400,
                    "cweName": "Uncontrolled Resource Consumption ('Resource Exhaustion')",
                    "description": "Affected versions of `timespan`...",
                    "recommendation": "No direct patch is available..."
                },
                "analysis": {
                    "state": "NOT_SET",
                    "isSuppressed": false
                },
                "matrix": "ca4f2da9-0fad-4a13-92d7-f627f3168a56:b815b581-fec1-4374-a871-68862a8f8d52:115b80bb-46c4-41d1-9f10-8a175d4abb46"
            },
            {
                "component": {
                    "uuid": "979f87f5-eaf5-4095-9d38-cde17bf9228e",
                    "name": "uglify-js",
                    "version": "2.4.24",
                    "purl": "pkg:npm/uglify-js@2.4.24"
                },
                "vulnerability": {
                    "uuid": "701a3953-666b-4b7a-96ca-e1e6a3e1def3",
                    "source": "NPM",
                    "vulnId": "48",
                    "title": "Regular Expression Denial of Service",
                    "subtitle": "uglify-js",
                    "severity": "LOW",
                    "severityRank": 3,
                    "cweId": 400,
                    "cweName": "Uncontrolled Resource Consumption ('Resource Exhaustion')",
                    "description": "Versions of `uglify-js` prior to...",
                    "recommendation": "Update to version 2.6.0 or later."
                },
                "analysis": {
                    "isSuppressed": false
                },
                "matrix": "ca4f2da9-0fad-4a13-92d7-f627f3168a56:979f87f5-eaf5-4095-9d38-cde17bf9228e:701a3953-666b-4b7a-96ca-e1e6a3e1def3"
            }]
    }
    """

    def _convert_dependency_track_severity_to_dojo_severity(
        self, dependency_track_severity
    ):
        """
        Converts a Dependency Track severity to a DefectDojo severity.
        :param dependency_track_severity: The severity from Dependency Track
        :return: A DefectDojo severity if a mapping can be found; otherwise a null value is returned
        """
        severity = dependency_track_severity.lower()
        if severity == "critical":
            return "Critical"
        elif severity == "high":
            return "High"
        elif severity == "medium":
            return "Medium"
        elif severity == "low":
            return "Low"
        elif severity.startswith("info"):
            return "Informational"
        else:
            return None

    def _convert_dependency_track_finding_to_dojo_finding(
        self, dependency_track_finding, test
    ):
        """
        Converts a Dependency Track finding to a DefectDojo finding

        :param dependency_track_finding: A dictionary representing a single finding from a Dependency Track Finding Packaging Format (FPF) export
        :param test: The test that the DefectDojo finding should be associated to
        :return: A DefectDojo Finding model
        """
        # Validation of required fields
        if "vulnerability" not in dependency_track_finding:
            raise Exception("Missing 'vulnerability' node from finding!")
        if "vulnId" not in dependency_track_finding["vulnerability"]:
            raise Exception("Missing 'vulnId' node from vulnerability!")
        vuln_id = dependency_track_finding["vulnerability"]["vulnId"]
        if "source" not in dependency_track_finding["vulnerability"]:
            raise Exception("Missing 'source' node from vulnerability!")
        source = dependency_track_finding["vulnerability"]["source"]
        if "component" not in dependency_track_finding:
            raise Exception("Missing 'component' node from finding!")
        if "name" not in dependency_track_finding["component"]:
            raise Exception("Missing 'name' node from component!")
        component_name = dependency_track_finding["component"]["name"]

        # Build the title of the Dojo finding
        # Note: the 'version' of a component is not a requirement in the Dependency Track data model.
        # As such we only add in version information if it is present.
        if (
            "version" in dependency_track_finding["component"]
            and dependency_track_finding["component"]["version"] is not None
        ):
            component_version = dependency_track_finding["component"]["version"]
        else:
            component_version = None
        if component_version is not None:
            version_description = component_version
        else:
            version_description = ""

        title = "{component_name}:{version_description} affected by: {vuln_id} ({source})".format(
            vuln_id=vuln_id,
            source=source,
            version_description=version_description,
            component_name=component_name,
        )

        # The vulnId is not always a CVE (e.g. if the vulnerability is not from the NVD source)
        # So here we set the cve for the DefectDojo finding to null unless the source of the
        # Dependency Track vulnerability is NVD
        cve = vuln_id if source is not None and source.upper() == "NVD" else None

        # Default CWE to CWE-1035 Using Components with Known Vulnerabilities if there is no CWE
        if (
            "cweId" in dependency_track_finding["vulnerability"]
            and dependency_track_finding["vulnerability"]["cweId"] is not None
        ):
            cwe = dependency_track_finding["vulnerability"]["cweId"]
        else:
            cwe = 1035

        # Build the description of the Dojo finding
        # We already know (from above) that the version information is not always present
        if component_version is not None:
            component_description = (
                "Version {component_version} of the {component_name} component".format(
                    component_version=component_version, component_name=component_name
                )
            )
        else:
            component_description = "The {component_name} component".format(
                component_name=component_name
            )
        vulnerability_description = (
            "You are using a component with a known vulnerability. "
            "{component_description} is affected by the vulnerability with an id of {vuln_id} as "
            "identified by {source}.".format(
                component_description=component_description,
                vuln_id=vuln_id,
                source=source,
            )
        )
        # Append purl info if it is present
        if (
            "purl" in dependency_track_finding["component"]
            and dependency_track_finding["component"]["purl"] is not None
        ):
            component_purl = dependency_track_finding["component"]["purl"]
            vulnerability_description = (
                vulnerability_description
                + "\nThe purl of the affected component is: {purl}.".format(
                    purl=component_purl
                )
            )
            # there is no file_path in the report, but defect dojo needs it otherwise it skips deduplication:
            # see https://github.com/DefectDojo/django-DefectDojo/issues/3647
            # might be no longer needed in the future, and is not needed if people use the default
            # hash code dedupe config for this parser
            file_path = component_purl
        else:
            file_path = "unknown"

        # Append other info about vulnerability description info if it is present
        if (
            "title" in dependency_track_finding["vulnerability"]
            and dependency_track_finding["vulnerability"]["title"] is not None
        ):
            vulnerability_description = (
                vulnerability_description
                + "\nVulnerability Title: {title}".format(
                    title=dependency_track_finding["vulnerability"]["title"]
                )
            )
        if (
            "subtitle" in dependency_track_finding["vulnerability"]
            and dependency_track_finding["vulnerability"]["subtitle"] is not None
        ):
            vulnerability_description = (
                vulnerability_description
                + "\nVulnerability Subtitle: {subtitle}".format(
                    subtitle=dependency_track_finding["vulnerability"]["subtitle"]
                )
            )
        if (
            "description" in dependency_track_finding["vulnerability"]
            and dependency_track_finding["vulnerability"]["description"] is not None
        ):
            vulnerability_description = (
                vulnerability_description
                + "\nVulnerability Description: {description}".format(
                    description=dependency_track_finding["vulnerability"]["description"]
                )
            )
        if (
            "uuid" in dependency_track_finding["vulnerability"]
            and dependency_track_finding["vulnerability"]["uuid"] is not None
        ):
            vuln_id_from_tool = dependency_track_finding["vulnerability"]["uuid"]

        # Get severity according to Dependency Track and convert it to a severity DefectDojo understands
        dependency_track_severity = dependency_track_finding["vulnerability"][
            "severity"
        ]
        vulnerability_severity = (
            self._convert_dependency_track_severity_to_dojo_severity(
                dependency_track_severity
            )
        )
        if vulnerability_severity is None:
            logger.warn(
                "Detected severity of %s that could not be mapped for %s. Defaulting to Critical!",
                dependency_track_severity,
                title,
            )
            vulnerability_severity = "Critical"

        # Use the analysis state from Dependency Track to determine if the finding has already been marked as a false positive upstream
        analysis = dependency_track_finding.get("analysis")
        is_false_positive = (
            True
            if analysis is not None and analysis.get("state") == "FALSE_POSITIVE"
            else False
        )

        # Build and return Finding model
        return Finding(
            title=title,
            test=test,
            cwe=cwe,
            cve=cve,
            active=False,
            verified=False,
            description=vulnerability_description,
            severity=vulnerability_severity,
            numerical_severity=Finding.get_numerical_severity(vulnerability_severity),
            false_p=is_false_positive,
            component_name=component_name,
            component_version=component_version,
            file_path=file_path,
            vuln_id_from_tool=vuln_id_from_tool,
            static_finding=True,
            dynamic_finding=False,
        )

    def get_findings(self, file, test):

        # Exit if file is not provided
        if file is None:
            return list()

        # Load the contents of the JSON file into a dictionary
        data = file.read()
        try:
            findings_export_dict = json.loads(str(data, "utf-8"))
        except:
            findings_export_dict = json.loads(data)

        # Exit if file is an empty JSON dictionary
        if len(findings_export_dict.keys()) == 0:
            return list()

        # Make sure the findings key exists in the dictionary and that it is not null or an empty list
        # If it is null or an empty list then exit
        if (
            "findings" not in findings_export_dict
            or not findings_export_dict["findings"]
        ):
            return list()

        # Start with an empty list of findings
        items = list()

        # If we have gotten this far then there should be one or more findings
        # Loop through each finding from Dependency Track
        for dependency_track_finding in findings_export_dict["findings"]:
            # Convert a Dependency Track finding to a DefectDojo finding
            dojo_finding = self._convert_dependency_track_finding_to_dojo_finding(
                dependency_track_finding, test
            )

            # Append DefectDojo finding to list
            items.append(dojo_finding)
        return items
