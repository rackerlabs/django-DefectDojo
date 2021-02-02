import hashlib
import re
from urllib.parse import urlparse
from xml.dom import NamespaceErr

from defusedxml import ElementTree as ET

from dojo.models import Endpoint, Finding

__author__ = "dr3dd589"


class Severityfilter:
    def __init__(self):
        self.severity_mapping = {"4": "Info", "3": "Low", "2": "Medium", "1": "High"}
        self.severity = None

    def eval_column(self, column_value):
        if column_value in list(self.severity_mapping.keys()):
            self.severity = self.severity_mapping[column_value]
        else:
            self.severity = "Info"


class WapitiXMLParser(object):
    def get_findings(self, file, test):

        if file is None:
            return list()

        tree = ET.parse(file)
        # get root of tree.
        root = tree.getroot()
        # check if it is
        if "report" not in root.tag:
            raise NamespaceErr("This doesn't seem to be a valid Wapiti xml file.")

        dupes = dict()
        for result in root.findall("report/results/result"):
            family = result.find("nvt/family").text
            # check if vulnerability found in family then proceed.
            if "vulnerability" in family:
                # get host
                host = result.find("host").text
                # get title
                title = result.find("nvt/name").text
                # get cve
                cve = result.find("nvt/cve").text
                # get numerical severity.
                num_severity = result.find("nvt/risk_factor").text
                severityfilter = Severityfilter()
                severityfilter.eval_column(num_severity)
                severity = severityfilter.severity
                # get reference
                reference = result.find("nvt/xref").text
                # get description and encode to utf-8.
                description = result.find("description").text
                mitigation = "N/A"
                impact = "N/A"
                # make dupe hash key
                dupe_key = hashlib.md5(
                    str(description + title + severity).encode("utf-8")
                ).hexdigest()
                # check if dupes are present.
                if dupe_key in dupes:
                    finding = dupes[dupe_key]
                    if finding.description:
                        finding.description = finding.description
                    self.process_endpoints(finding, host)
                    dupes[dupe_key] = finding
                else:
                    dupes[dupe_key] = True

                    finding = Finding(
                        title=title,
                        test=test,
                        active=False,
                        verified=False,
                        cve=cve,
                        description=description,
                        severity=severity,
                        numerical_severity=Finding.get_numerical_severity(severity),
                        mitigation=mitigation,
                        impact=impact,
                        references=reference,
                        dynamic_finding=True,
                    )

                    dupes[dupe_key] = finding
                    self.process_endpoints(finding, host)

        return list(dupes.values())

    def process_endpoints(self, finding, host):
        protocol = "http"
        query = ""
        fragment = ""
        path = ""
        url = urlparse(host)

        if url:
            path = url.path
            if path == host:
                path = ""

        rhost = re.match(
            r"(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
            host,
        )
        try:
            protocol = rhost[1]
            host = rhost[4]
        except:
            pass
        try:
            dupe_endpoint = Endpoint.objects.get(
                protocol=protocol, host=host, query=query, fragment=fragment, path=path
            )
        except Endpoint.DoesNotExist:
            dupe_endpoint = None

        if not dupe_endpoint:
            endpoint = Endpoint(
                protocol=protocol, host=host, query=query, fragment=fragment, path=path
            )
        else:
            endpoint = dupe_endpoint

        if not dupe_endpoint:
            endpoints = [endpoint]
        else:
            endpoints = [endpoint, dupe_endpoint]

        finding.unsaved_endpoints = finding.unsaved_endpoints + endpoints
