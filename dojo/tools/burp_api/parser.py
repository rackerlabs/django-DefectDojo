import json
import logging
from urllib.parse import urlparse

from dojo.models import Endpoint, Finding

logger = logging.getLogger(__name__)


DESCRIPTION_TEMPLATE = """**{title}**
**Serial Number**: {serial_number}
**Type Index**: {type_index}
**Confidence**: {confidence}
**Description**: {description_text}
"""


class BurpApiParser(object):
    """Parser that can load data from Burp API"""

    def get_findings(self, file, test):

        if file is None:
            return

        # API export is a JSON file
        tree = json.load(file)

        # by default give the test a title
        test.title = "Burp REST API"

        items = []
        # for each issue found
        for issue_event in tree.get("issue_events", list()):
            if "issue_found" == issue_event.get("type") and "issue" in issue_event:
                issue = issue_event.get("issue")

                title = issue.get("name", "Burp issue")
                severity = convert_severity(issue)
                description_formated = DESCRIPTION_TEMPLATE.format(
                    title=title,
                    serial_number=issue.get("serial_number", "<None>"),
                    type_index=issue.get("type_index", "<None>"),
                    confidence=issue.get("confidence", "<None>"),
                    description_text=issue.get("description", "<None>"),
                )
                false_p = False
                # manage special case of false positives
                if "false_positive" == issue.get("severity", "undefined"):
                    false_p = True

                finding = Finding(
                    title=title,
                    test=test,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    description=description_formated,
                    mitigation="No mitigation provided",
                    references="No references provided",
                    cve=None,
                    cwe=0,
                    active=True,
                    verified=False,
                    false_p=false_p,
                    duplicate=False,
                    out_of_scope=False,
                    mitigated=None,
                    impact="No impact provided",
                    static_finding=False,  # by definition
                    dynamic_finding=True,  # by definition
                    unique_id_from_tool=str(
                        issue.get("serial_number", "")
                    ),  # the serial number is a good candidate for this attribute
                    vuln_id_from_tool=str(
                        issue.get("type_index", "")
                    ),  # the type index is a good candidate for this attribute
                )
                # manage confidence
                if convert_confidence(issue) is not None:
                    finding.scanner_confidence = convert_confidence(issue)
                # manage endpoints
                if "origin" in issue and "path" in issue:
                    parts = urlparse(issue.get("origin") + issue.get("path"))
                    finding.unsaved_endpoints = [
                        Endpoint(
                            protocol=parts.scheme,
                            host=parts.netloc,
                            path=parts.path,
                            query=parts.query,
                            fragment=parts.fragment,
                            product=test.engagement.product,
                        )
                    ]
                items.append(finding)
        return items


def convert_severity(issue):
    """According to OpenAPI definition of the API

    "Severity":{
             "type":"string",
             "enum":[
                "high",
                "medium",
                "low",
                "info",
                "undefined",
                "false_positive"
             ]
          },
    """
    value = issue.get("severity", "info").lower()
    if value in ["high", "medium", "low", "info"]:
        return value.title()
    return "Info"


def convert_confidence(issue):
    """According to OpenAPI definition:

    "Confidence":{
             "type":"string",
             "enum":[
                "certain",
                "firm",
                "tentative",
                "undefined"
             ]
          },
    """
    value = issue.get("confidence", "undefined").lower()
    if "certain" == value:
        return 2
    elif "firm" == value:
        return 3
    elif "tentative" == value:
        return 6
    else:
        return None
