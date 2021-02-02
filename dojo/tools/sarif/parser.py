import json
import logging
import re
from datetime import datetime

from dojo.models import Finding

logger = logging.getLogger(__name__)

CWE_REGEX = r"cwe-\d+$"


class SarifParser(object):
    """OASIS Static Analysis Results Interchange Format (SARIF) for version 2.1.0 only.

    https://www.oasis-open.org/committees/tc_home.php?wg_abbrev=sarif
    """

    def get_findings(self, filehandle, test):
        tree = json.load(filehandle)

        # by default give the test a title linked to the first tool in the report
        test.title = f"SARIF ({tree['runs'][0]['tool']['driver']['name']})"
        return self.get_items(tree, test)

    def get_items(self, tree, test):
        items = list()
        # for each runs
        for run in tree.get("runs", list()):
            # load rules
            rules = get_rules(run)
            artifacts = get_artifacts(run)
            for result in run.get("results", list()):
                item = get_item(result, rules, artifacts, test)
                items.append(item)
        return items


def get_rules(run):
    rules = {}
    for item in run["tool"]["driver"].get("rules", []):
        rules[item["id"]] = item
    return rules


def get_rule_tags(rule):
    if "properties" not in rule:
        return []
    if "tags" not in rule["properties"]:
        return []
    else:
        return rule["properties"]["tags"]


def get_rule_cwes(rule):
    cwes = []
    for tag in get_rule_tags(rule):
        matches = re.search(CWE_REGEX, tag, re.IGNORECASE)
        if matches:
            cwes.append(int(matches[0].split("-")[1]))
    return cwes


def get_artifacts(run):
    artifacts = {}
    custom_index = 0  # hack because some tool doesn't generate this attribute
    for tree_artifact in run.get("artifacts", []):
        artifacts[tree_artifact.get("index", custom_index)] = tree_artifact
        custom_index += 1
    return artifacts


def get_severity(data):
    """Convert level value to severity"""
    if "warning" == data:
        return "Medium"
    elif "error" == data:
        return "Critical"
    else:
        return "Info"


def get_message_from_multiformatMessageString(data, rule):
    if rule is not None and "id" in data:
        return rule["messageStrings"][data["id"]]
    else:
        # TODO manage markdown
        return data.get("text")


def get_item(result, rules, artifacts, test):
    mitigation = result.get("Remediation", {}).get("Recommendation", {}).get("Text", "")
    references = result.get("Remediation", {}).get("Recommendation", {}).get("Url")
    verified = False
    false_p = False
    duplicate = False
    out_of_scope = False
    impact = None

    if result.get("Compliance", {}).get("Status", "PASSED"):
        if result.get("LastObservedAt", None):
            try:
                mitigated = datetime.strptime(
                    result.get("LastObservedAt"), "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except:
                mitigated = datetime.strptime(
                    result.get("LastObservedAt"), "%Y-%m-%dT%H:%M:%fZ"
                )
        else:
            mitigated = datetime.utcnow()
    else:
        mitigated = None

    # if there is a location get it
    file_path = None
    line = -1
    if "locations" in result:
        location = result["locations"][0]
        if "physicalLocation" in location:
            file_path = location["physicalLocation"]["artifactLocation"]["uri"]
            # 'region' attribute is optionnal
            if "region" in location["physicalLocation"]:
                line = location["physicalLocation"]["region"]["startLine"]

    # test rule link
    rule = rules.get(result["ruleId"])
    title = result["ruleId"]
    if "message" in result:
        title = get_message_from_multiformatMessageString(result["message"], rule)
    description = ""
    severity = get_severity("warning")
    if rule is not None:
        # get the severity from the rule
        if "defaultConfiguration" in rule:
            severity = get_severity(
                rule["defaultConfiguration"].get("level", "warning")
            )

        if "shortDescription" in rule:
            title = get_message_from_multiformatMessageString(
                rule["shortDescription"], rule
            )
            description = get_message_from_multiformatMessageString(
                rule["shortDescription"], rule
            )
        else:
            title = result["message"].get("text", "No text")
            description = get_message_from_multiformatMessageString(
                rule["fullDescription"], rule
            )

    # we add a special 'None' case if there is no CWE
    cwes = [0]
    if rule is not None:
        cwes_extracted = get_rule_cwes(rule)
        if len(cwes_extracted) > 1:
            cwes = cwes_extracted

    for cwe in cwes:
        finding = Finding(
            title=title,
            test=test,
            severity=severity,
            numerical_severity=Finding.get_numerical_severity(severity),
            description=description,
            mitigation=mitigation,
            references=references,
            cve=None,  # for now CVE are not managed or it's not very clear how in the spec
            cwe=cwe,
            active=True,
            verified=verified,
            false_p=false_p,
            duplicate=duplicate,
            out_of_scope=out_of_scope,
            mitigated=mitigated,
            impact="No impact provided",
            static_finding=True,  # by definition
            dynamic_finding=False,  # by definition
            file_path=file_path,
            line=line,
        )

    return finding
