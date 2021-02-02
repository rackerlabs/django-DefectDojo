import hashlib
import json

from dojo.models import Finding

__author__ = "dr3dd589"


class WhitesourceJSONParser(object):
    def get_findings(self, file, test):
        if file is None:
            return list()

        data = file.read()
        try:
            content = json.loads(str(data, "utf-8"))
        except:
            content = json.loads(data)

        def _build_common_output(node, lib_name=None):
            # project only available in manual export
            # name --> CVE in manual, library name in pipeline
            project = ""
            cve = None
            component_name = None
            component_version = None
            if "library" in node:
                project = node.get("project")
                description = (
                    "**Description** : "
                    + node.get("description", "")
                    + "\n\n"
                    + "**Library Name** : "
                    + node["library"].get("name", "")
                    + "\n\n"
                    + "**Library Filename** : "
                    + node["library"].get("filename", "")
                    + "\n\n"
                    + "**Library Description** : "
                    + node["library"].get("description", "")
                    + "\n\n"
                    + "**Library Type** : "
                    + node["library"].get("type", "")
                    + "\n"
                )
                lib_name = node["library"].get("filename")
                component_name = node["library"].get("artifactId")
                component_version = node["library"].get("version")
            else:
                description = node.get("description")

            cve = node.get("name")
            if cve is None:
                title = "CVE-None | " + lib_name
            else:
                title = cve + " | " + lib_name
            # cvss2 by default in CLI, but cvss3 in UI. Adapting to have homogeneous behavior.
            if "cvss3_severity" in node:
                cvss_sev = node.get("cvss3_severity")
            else:
                cvss_sev = node.get("severity")
            severity = cvss_sev.lower().capitalize()

            cvss3_score = node.get("cvss3_score", "N/A")
            cvss3_vector = node.get("scoreMetadataVector", "N/A")
            severity_justification = "CVSS v3 score: {} ({})".format(
                cvss3_score, cvss3_vector
            )
            cwe = 1035  # default OWASP a9 until the report actually has them

            mitigation = "N/A"
            if "topFix" in node:
                try:
                    topfix_node = node.get("topFix")
                    mitigation = "**Resolution** ({}): {}\n".format(
                        topfix_node.get("date"), topfix_node.get("fixResolution")
                    )
                except Exception as e:
                    print("Error handling topFix node. {}").format(e)

            filepaths = []
            if "sourceFiles" in node:
                try:
                    sourceFiles_node = node.get("sourceFiles")
                    for sfile in sourceFiles_node:
                        filepaths.append(sfile.get("localPath"))
                except Exception as e:
                    print("Error handling local paths for vulnerability. {}").format(e)

            return {
                "title": title,
                "description": description,
                "severity": severity,
                "mitigation": mitigation,
                "cve": cve,
                "cwe": cwe,
                "severity_justification": severity_justification,
                "file_path": ", ".join(filepaths),
                "component_name": component_name,
                "component_version": component_version,
            }

        def _dedup_and_create_finding(dupes, vuln):
            dupe_key = hashlib.md5(
                vuln.get("description").encode("utf-8")
                + vuln.get("title").encode("utf-8")
            ).hexdigest()

            if dupe_key in dupes:
                finding = dupes[dupe_key]
                if finding.description:
                    finding.description = finding.description
                dupes[dupe_key] = finding
            else:
                dupes[dupe_key] = True

                finding = Finding(
                    title=vuln.get("title"),
                    test=test,
                    description=vuln.get("description"),
                    severity=vuln.get("severity"),
                    cve=vuln.get("cve"),
                    cwe=vuln.get("cwe"),
                    mitigation=vuln.get("mitigation"),
                    numerical_severity=Finding.get_numerical_severity(
                        vuln.get("severity")
                    ),
                    references=vuln.get("references"),
                    file_path=vuln.get("file_path"),
                    component_name=vuln.get("component_name"),
                    component_version=vuln.get("component_version"),
                    severity_justification=vuln.get("severity_justification"),
                    dynamic_finding=True,
                )

                dupes[dupe_key] = finding

        output = []
        if "libraries" in content:
            # we are likely dealing with a report generated from CLI with -generateScanReport,
            # which will output vulnerabilities as an array of a library
            # In this scenario, build up a an array
            tree_libs = content.get("libraries")
            for lib_node in tree_libs:
                # get the overall lib info here, before going into vulns
                if (
                    "vulnerabilities" in lib_node
                    and len(lib_node.get("vulnerabilities")) > 0
                ):
                    for vuln in lib_node.get("vulnerabilities"):
                        output.append(_build_common_output(vuln, lib_node.get("name")))

        elif "vulnerabilities" in content:
            # likely a manual json export for vulnerabilities only for a project.
            # Vulns are standalone, and library is a property.
            tree_node = content["vulnerabilities"]
            for node in tree_node:
                output.append(_build_common_output(node))

        dupes = dict()
        for vuln in output:
            _dedup_and_create_finding(dupes, vuln)

        return dupes.values()
