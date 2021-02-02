import hashlib
import re
from urllib.parse import urlparse
from xml.dom import NamespaceErr

import html2text
from defusedxml import ElementTree as ET

from dojo.models import Endpoint, Finding


class MicrofocusWebinspectXMLParser(object):
    """Micro Focus Webinspect XML report parser"""

    def get_findings(self, file, test):

        tree = ET.parse(file)
        # get root of tree.
        root = tree.getroot()
        if "Sessions" not in root.tag:
            raise NamespaceErr("This doesn't seem to be a valid Webinspect xml file.")

        dupes = dict()
        for session in root:
            url = session.find("URL").text
            parts = urlparse(url)
            endpoint = Endpoint(
                protocol=parts.scheme,
                host=parts.netloc,
                path=parts.path,
                query=parts.query,
                fragment=parts.fragment,
                product=test.engagement.product,
            )
            issues = session.find("Issues")
            for issue in issues.findall("Issue"):
                unique_id_from_tool = issue.attrib.get("id", None)
                title = issue.find("Name").text
                description = ""
                mitigation = ""
                reference = ""
                severity = MicrofocusWebinspectXMLParser.convert_severity(
                    issue.find("Severity").text
                )
                for content in issue.findall("ReportSection"):
                    name = content.find("Name").text
                    if "Summary" in name:
                        if content.find("SectionText").text:
                            description = content.find("SectionText").text
                    if "Fix" in name:
                        if content.find("SectionText").text:
                            mitigation = content.find("SectionText").text
                    if "Reference" in name:
                        if name and content.find("SectionText").text:
                            reference = html2text.html2text(
                                content.find("SectionText").text
                            )
                cwe = 0
                description = ""
                classifications = issue.find("Classifications")
                for content in classifications.findall("Classification"):
                    # detect CWE number
                    # TODO support more than one CWE number
                    if "kind" in content.attrib and "CWE" == content.attrib["kind"]:
                        cwe = MicrofocusWebinspectXMLParser.get_cwe(
                            content.attrib["identifier"]
                        )
                        description += "\n\n" + content.text + "\n"

                # make dupe hash key
                dupe_key = hashlib.md5(
                    str(description + title + severity).encode("utf-8")
                ).hexdigest()
                # check if dupes are present.
                if dupe_key in dupes:
                    finding = dupes[dupe_key]
                    if finding.description:
                        finding.description = finding.description
                    dupes[dupe_key] = finding
                else:
                    dupes[dupe_key] = True

                    finding = Finding(
                        title=title,
                        test=test,
                        active=False,
                        verified=False,
                        cwe=cwe,
                        description=description,
                        severity=severity,
                        numerical_severity=Finding.get_numerical_severity(severity),
                        mitigation=mitigation,
                        references=reference,
                        static_finding=False,
                        dynamic_finding=True,
                    )
                    if "id" in issue.attrib:
                        finding.unique_id_from_tool = issue.attrib.get("id")
                    # manage endpoint
                    finding.unsaved_endpoints.append(endpoint)
                    dupes[dupe_key] = finding

        return list(dupes.values())

    @staticmethod
    def convert_severity(val):
        if val == "0":
            return "Info"
        elif val == "1":
            return "Low"
        elif val == "2":
            return "Medium"
        elif val == "3":
            return "High"
        else:
            return "Info"

    @staticmethod
    def get_cwe(val):
        # Match only the first CWE!
        cweSearch = re.search("CWE-(\\d+)", val, re.IGNORECASE)
        if cweSearch:
            return int(cweSearch.group(1))
        else:
            return 0
