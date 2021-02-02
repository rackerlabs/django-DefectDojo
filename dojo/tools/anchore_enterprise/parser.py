import json
import logging
import re
from datetime import datetime
from json.decoder import JSONDecodeError

from dojo.models import Finding

logger = logging.getLogger(__name__)


class AnchoreEnterprisePolicyCheckParser:
    def get_findings(self, filename, test):
        content = filename.read()
        try:
            data = json.loads(str(content, "utf-8"))
        except (JSONDecodeError, TypeError):
            data = json.loads(content)

        find_date = datetime.now()
        items = list()
        try:
            for checks in data:
                for policies in checks.values():
                    for images in policies.values():
                        for evaluation in images:
                            try:
                                results = evaluation["detail"]["result"]
                                imageid = results["image_id"]
                                imageids = results["result"]
                                imagechecks = imageids[imageid]
                                rows = imagechecks["result"]["rows"]
                                for row in rows:
                                    repo, tag = row[1].split(":", 2)
                                    description = row[5]
                                    severity = map_gate_action_to_severity(row[6])
                                    policyid = row[8]
                                    policyname = policy_name(
                                        evaluation["detail"]["policy"]["policies"],
                                        policyid,
                                    )
                                    gate = row[3]
                                    triggerid = row[2]
                                    cve = extract_cve(triggerid)
                                    title = (
                                        policyname
                                        + " - gate|"
                                        + gate
                                        + " - trigger|"
                                        + triggerid
                                    )
                                    find = Finding(
                                        title=title,
                                        test=test,
                                        cve=cve,
                                        description=description,
                                        severity=severity,
                                        numerical_severity=Finding.get_number_severity(
                                            severity
                                        ),
                                        references="Policy ID: {}\nTrigger ID: {}".format(
                                            policyid, triggerid
                                        ),
                                        file_path=search_filepath(description),
                                        component_name=repo,
                                        component_version=tag,
                                        date=find_date,
                                        static_finding=True,
                                        dynamic_finding=False,
                                    )
                                    items.append(find)
                            except (KeyError, IndexError) as err:
                                raise Exception(
                                    "Invalid format: {} key not found".format(err)
                                )
        except AttributeError as err:
            # import empty policies without error (e.g. policies or images objects are not a dictionary)
            logger.warning("Exception at %s", "parsing anchore policy", exc_info=err)
        return items


def map_gate_action_to_severity(gate):
    gate_action_to_severity = {
        "stop": "Critical",
        "warn": "Medium",
    }
    if gate in gate_action_to_severity:
        return gate_action_to_severity[gate]
    return "Low"


def policy_name(policies, policy_id):
    for policy in policies:
        if policy_id == policy["id"]:
            return policy["name"]
    return "unknown"


def extract_cve(trigger_id):
    try:
        cve, _ = trigger_id.split("+", 2)
        if cve.startswith("CVE"):
            return cve
        return ""
    except ValueError:
        return ""


def search_filepath(text):
    match = re.search(r" (/[^/ ]*)+/?", text)
    path = ""
    if match:
        try:
            path = match.group(0)
        except IndexError:
            path = ""
    return path.strip()
