# Author: apipia, wheelsvt
from .importer import BlackduckCRImporter
from dojo.models import Finding


class BlackduckHubParser(object):
    """
    Can import as exported from Blackduck:
    - from a zip file containing a security.csv, sources.csv and components.csv
    """

    def get_findings(self, filename, test):
        """
        Function initializes the parser with a file and sets the
        self.items (eventually).
        :param filename: Input in Defect Dojo
        :param test:
        """
        components, securities, sources = self.import_data(filename)
        return self.ingest_findings(components, securities, sources, test)

    def import_data(self, filename) -> (dict, dict, dict):
        """
        Calls the Importer from dojo/tools/blackduck_component_risk/importer to
        parse through the zip file and export needed information from the
        three relevant files (security, source and components).
        :param filename: Name of the zipfile. Passed in via Defect Dojo
        :return: Returns a tuple of dictionaries, Components and Securities.
        """
        importer = BlackduckCRImporter()

        components, securities, sources = importer.parse_findings(filename)
        return components, securities, sources

    def ingest_findings(self, components, securities, sources, test):
        """
        Takes the components and securities from the importer that parsed the zip file, and
        iterates over them, creating findings.
        :param components: Dictionary containing all components from the components csv
        :param securities: Dictionary containing all security vulnerabilities for each component
        :param sources: Dictionary containing all sources data from the sources csv
        :param test:
        :return:
        """
        items = []
        # License Risk
        license_risk = []
        for component_id, component in components.items():
            source = {}
            # Find the sources.csv data for this component
            for id, src in sources.items():
                if id in component_id:
                    source = src
            if component.get("Component policy status") == "In Violation":
                # We have us a license risk:
                title = self.license_title(component)
                description = self.license_description(component, source)
                severity = "High"
                mitigation = self.license_mitigation(component)
                impact = "N/A"
                references = self.license_references(component)
                finding = Finding(
                    title=title,
                    test=test,
                    active=False,
                    verified=False,
                    description=description,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    static_finding=True,
                    unique_id_from_tool=component_id,
                )
                license_risk.append(finding)
            elif "None" not in self.license_severity(component):
                # We have a license risk for review, but not directly "In Violation"
                title = "Review " + self.license_title(component)
                description = self.license_description(component, source)
                severity = self.license_severity(component)
                mitigation = self.license_mitigation(component, False)
                impact = "N/A"
                references = self.license_references(component)
                finding = Finding(
                    title=title,
                    test=test,
                    active=False,
                    verified=False,
                    description=description,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    static_finding=True,
                    unique_id_from_tool=component_id,
                )
                license_risk.append(finding)
        items.extend(license_risk)

        # Security Risk
        security_risk = []
        for component_id, vulns in securities.items():
            title = self.security_title(vulns)
            description = self.security_description(vulns)
            severity = self.security_severity(vulns)
            mitigation = self.security_mitigation(vulns)
            impact = self.security_impact(vulns)
            references = self.security_references(vulns)
            file_path = self.security_filepath(vulns)

            finding = Finding(
                title=title,
                test=test,
                active=False,
                verified=False,
                description=description,
                severity=severity,
                numerical_severity=Finding.get_numerical_severity(severity),
                mitigation=mitigation,
                impact=impact,
                references=references,
                static_finding=True,
                file_path=file_path,
                unique_id_from_tool=component_id,
            )
            security_risk.append(finding)
        items.extend(security_risk)
        return items

    def license_title(self, component):
        """
        Uses the Component name and Component version name. The Origin id is sometimes blank,
        however it seems that component name and version name isn't.
        :param component: Dictionary containing all components.
        :return:
        """
        return "License Risk: {}:{}".format(
            component.get("Component name"), component.get("Component version name")
        )

    def license_description(self, component, source):
        """
        Pulls out all important information from the components CSV regarding the License in use.
        :param component: Dictionary containing all components.
        :return:
        """
        desc = "**License Name:** {}  \n".format(component.get("License names"))
        desc += "**License Families:** {}  \n".format(component.get("License families"))
        desc += "**License Usage:** {}  \n".format(component.get("Usage"))
        desc += "**License Origin name:** {} \n".format(component.get("Origin name"))
        desc += "**License Origin id:** {} \n".format(component.get("Origin id"))
        desc += "**Match type:** {}\n".format(component.get("Match type"))
        try:
            desc += "**Path:** {}\n".format(source.get("Path"))
            desc += "**Archive context:** {}\n".format(source.get("Archive context"))
            desc += "**Scan:** {}\n".format(source.get("Scan"))
        except KeyError:
            desc += "**Path:** Unable to find path in source data."
            desc += (
                "**Archive context:** Unable to find archive context in source data."
            )
            desc += "**Scan:** Unable to find scan in source data."
        return desc

    def license_mitigation(self, component, violation=True):
        """
        Uses Component name and Component version name to display the package.
        :param component: Dictionary containing all components.
        :param violation: Boolean indicating if this is a violation or for review
        :return:
        """
        mit = ""
        if violation:
            mit = "Package has a license that is In Violation and should not be used: {}:{}.  ".format(
                component.get("Component name"), component.get("Component version name")
            )
            mit += "Please use another component with an acceptable license."
        else:
            mit = "Package has a potential license risk and should be reviewed: {}:{}. ".format(
                component.get("Component name"), component.get("Component version name")
            )
            mit += "A legal review may indicate that another component should be used with an acceptable license."
        return mit

    def license_references(self, component):
        return "**Project:** {}\n".format(component.get("Project path"))

    def security_title(self, vulns):
        """
        Creates the Title using the Component name and Component version name.
        These should be identical for each vuln in the list.
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        title = "Security Risk: {}:{}".format(
            vulns[0]["Component name"], vulns[0]["Component version name"]
        )
        return title

    def security_description(self, vulns):
        """
        Markdown formated description that displays information about each CVE found in the
        csv file for a given component.
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        desc = (
            "#Vulnerabilities \nThis component version contains the following "
            "vulnerabilities:\n\n"
        )
        for vuln in vulns:
            desc += "###{}  \n".format(vuln["Vulnerability id"])
            desc += (
                "**Base Score:** {} \n**Exploitability:** {} \n**Impact:** {}\n".format(
                    vuln["Base score"], vuln["Exploitability"], vuln["Impact"]
                )
            )
            # Not all have a URL
            if vuln["URL"] != "":
                desc += "**URL:** [{}]({})\n".format(
                    vuln["Vulnerability id"], vuln["URL"]
                )
            desc += "**Description:** {}\n".format(vuln["Description"])
        return desc

    def license_severity(self, component):
        """
        Iterates over all base_scores of each vulnerability and picks the max. A map is used to
        map the all-caps format of the CSV with the case that Defect Dojo expects.
        (Could use a .lower() or ignore_case during comparison)
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        map = {
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
            "INFO": "Info",
            "CRITICAL": "Critical",
            "OK": "None",
        }
        sev = "None"
        try:
            sev = map[component.get("License Risk")]
        except KeyError:
            sev = "None"
        return sev

    def security_severity(self, vulns):
        """
        Iterates over all base_scores of each vulnerability and picks the max. A map is used to
        map the all-caps format of the CSV with the case that Defect Dojo expects.
        (Could use a .lower() or ignore_case during comparison)
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        map = {
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
            "INFO": "Info",
            "CRITICAL": "Critical",
        }
        max_severity = 0.0
        sev = "Info"
        for vuln in vulns:
            if float(vuln["Base score"]) > max_severity:
                max_severity = float(vuln["Base score"])
                sev = map[vuln["Security Risk"]]
        return sev

    def security_mitigation(self, vulns):
        """
        Mitigation is always "update package", that the entire point of Blackduck, to identify
        when projects are using vulnerable versions of components. Mitigation is to update the
        package. Identifies the component with name:version_name.
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        mit = "Update component {}:{} to a secure version".format(
            vulns[0]["Component name"], vulns[0]["Component version name"]
        )
        return mit

    def security_impact(self, vulns):
        """
        Each vuln has an impact ratiing, so I figured I would iterate over and pull out the
        largest value.
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        max_impact = 0.0
        for vuln in vulns:
            if float(vuln["Impact"]) > max_impact:
                max_impact = float(vuln["Impact"])
        return max_impact

    def security_references(self, vulns):
        """
        Takes all of the URL fields out of the csv, not all findings will have a URL, so it will
        only create it for those that do.
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        references = "**Project:** {}\n".format(vulns[0]["Project path"])
        for vuln in vulns:
            if vuln["URL"] != "":
                references += "{}: [{}]({})\n".format(
                    vuln["Vulnerability id"], vuln["URL"], vuln["URL"]
                )
        return references

    def security_filepath(self, vulns):
        """
        The origin name (maven, github, npmjs, etc) and the component origin id is used. However,
        not all items will have an origin id, so to try to still match as closely as possible,
        "component_name/version" is used.
        1. origin:component_origin_id
        2. origin:component_name/version
        :param vulns: Dictionary {component_version_identifier: [vulns]}
        :return:
        """
        if vulns[0]["Component origin id"] == "":
            component_key = "{}/{}".format(
                vulns[0]["Component name"], vulns[0]["Component version name"]
            )
        else:
            component_key = vulns[0]["Component origin id"]
        return "{}:{}".format(vulns[0]["Component origin name"], component_key)
