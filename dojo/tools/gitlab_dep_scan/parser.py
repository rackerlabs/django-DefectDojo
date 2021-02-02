import json

from dojo.models import Finding


class GitlabDepScanReportParser(object):
    def get_findings(self, json_output, test):
        if json_output is None:
            return

        tree = self.parse_json(json_output)
        if tree:
            return self.get_items(tree, test)

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

        for node in tree["vulnerabilities"]:
            item = get_item(node, test)
            if item:
                items[item.unique_id_from_tool] = item

        return list(items.values())


def get_item(vuln, test):
    if vuln["category"] != "dependency_scanning":
        # For Dependency Scanning reports, value must always be "dependency_scanning"
        return None

    unique_id_from_tool = None
    if "id" in vuln:
        unique_id_from_tool = vuln["id"]
    else:
        # If the new unique id is not provided, fall back to deprecated "cve" fingerprint (old version)
        unique_id_from_tool = vuln["cve"]

    title = ""
    if "name" in vuln:
        title = vuln["name"]
    elif "message" in vuln:
        title = vuln["message"]
    elif "description" in vuln:
        title = vuln["description"]
    else:
        # All other fields are optional, if none of them has a value, fall back on the unique id
        title = unique_id_from_tool

    description = "Scanner: {}\n".format(vuln["scanner"]["name"])
    if "message" in vuln:
        description += "{}\n".format(vuln["message"])
    if "description" in vuln:
        description += "{}\n".format(vuln["description"])

    location = vuln["location"]
    file_path = location["file"] if "file" in location else None
    sourcefile = location["file"] if "file" in location else None

    line = location["start_line"] if "start_line" in location else None
    if "end_line" in location:
        line = location["end_line"]

    sast_source_line = location["start_line"] if "start_line" in location else None

    sast_object = None
    if "class" in location and "method" in location:
        sast_object = "{}#{}".format(location["class"], location["method"])
    elif "class" in location:
        sast_object = location["class"]
    elif "method" in location:
        sast_object = location["method"]

    severity = vuln["severity"]
    if severity == "Undefined" or severity == "Unknown":
        # Severity can be "Undefined" or "Unknown" in report
        # In that case we set it as Info and specify the initial severity in the title
        title = "[{} severity] {}".format(severity, title)
        severity = "Info"
    numerical_severity = Finding.get_numerical_severity(severity)
    # Dependency Scanning analyzers doesn't provide confidence property
    # See https://docs.gitlab.com/ee/user/application_security/dependency_scanning/analyzers.html#analyzers-data
    scanner_confidence = False

    mitigation = ""
    if "solution" in vuln:
        mitigation = vuln["solution"]

    cwe = None
    cve = None
    references = ""
    if "identifiers" in vuln:
        for identifier in vuln["identifiers"]:
            if identifier["type"].lower() == "cwe":
                cwe = identifier["value"]
            elif identifier["type"].lower() == "cve":
                cve = identifier["value"]
            else:
                references += "Identifier type: {}\n".format(identifier["type"])
                references += "Name: {}\n".format(identifier["name"])
                references += "Value: {}\n".format(identifier["value"])
                if "url" in identifier:
                    references += "URL: {}\n".format(identifier["url"])
                references += "\n"

    finding = Finding(
        title=cve + ": " + title if cve else title,
        test=test,
        active=False,
        verified=False,
        description=description,
        severity=severity,
        numerical_severity=numerical_severity,
        scanner_confidence=scanner_confidence,
        mitigation=mitigation,
        unique_id_from_tool=unique_id_from_tool,
        references=references,
        file_path=file_path,
        sourcefile=sourcefile,
        line=line,
        sast_source_object=sast_object,
        sast_sink_object=sast_object,
        sast_source_file_path=file_path,
        sast_source_line=sast_source_line,
        cwe=cwe,
        cve=cve,
        static_finding=True,
        dynamic_finding=False,
    )

    return finding
