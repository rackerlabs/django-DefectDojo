import hashlib
import re
from urllib.parse import urlparse
from xml.dom import NamespaceErr

from defusedxml import ElementTree as ET

from dojo.models import Endpoint, Finding

__author__ = "dr3dd589"


class OpenscapXMLParser(object):
    def get_findings(self, file, test):
        tree = ET.parse(file)
        # get root of tree.
        root = tree.getroot()
        namespace = self.get_namespace(root)
        # go to test result
        test_result = tree.find("./{0}TestResult".format(namespace))
        ips = []
        # append all target in a list.
        for ip in test_result.findall("./{0}target-address".format(namespace)):
            ips.append(ip.text)
        # check if xml file hash correct root or not.
        if "Benchmark" not in root.tag:
            raise NamespaceErr(
                "This doesn't seem to be a valid Openscap vulnerability scan xml file."
            )
        dupes = dict()
        # run both rule, and rule-result in parallel so that we can get title for failed test from rule.
        for rule, rule_result in zip(
            root.findall("./{0}Rule".format(namespace)),
            test_result.findall("./{0}rule-result".format(namespace)),
        ):
            cves = []
            result = rule_result.find("./{0}result".format(namespace)).text
            # find only failed report.
            if "fail" in result:
                # get title of Rule corrosponding rule-result.
                title = rule.find("./{0}title".format(namespace)).text
                description = "**Title** : " + title + "\n\n"
                mitigation = "N/A"
                impact = "N/A"
                for cve in rule_result.findall("./{0}ident".format(namespace)):
                    cves.append(cve.text)
                # if finding has only one cve then ok. otherwise insert it in description field.
                if len(cves) > 1:
                    cve_desc = ""
                    for cve in cves:
                        cve_desc += (
                            "[{0}](https://cve.mitre.org/cgi-bin/cvename.cgi?name={0})".format(
                                cve
                            )
                            + ", "
                        )

                    description += "**Releted CVE's** : " + cve_desc[:-2]
                else:
                    try:
                        cve = cves[0]
                    except:
                        pass
                # get severity.
                severity = rule_result.attrib["severity"].lower().capitalize()
                check_content = rule_result.find(
                    "./{0}check/{0}check-content-ref".format(namespace)
                ).attrib
                # get references.
                references = (
                    "**name** : "
                    + check_content["name"]
                    + "\n"
                    + "**href** : "
                    + check_content["href"]
                    + "\n"
                )

                dupe_key = hashlib.md5(references.encode("utf-8")).hexdigest()

                if dupe_key in dupes:
                    finding = dupes[dupe_key]
                    if finding.references:
                        finding.references = finding.references
                    for ip in ips:
                        self.process_endpoints(finding, ip)
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
                        references=references,
                        dynamic_finding=True,
                    )

                    dupes[dupe_key] = finding
                    for ip in ips:
                        self.process_endpoints(finding, ip)

        return list(dupes.values())

    # this function is extract namespace present in xml file.
    def get_namespace(self, element):
        m = re.match(r"\{.*\}", element.tag)
        return m.group(0) if m else ""

    # this function create endpoints with url parsing.

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

        rhost = re.search(
            r"(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
            host,
        )
        try:
            protocol = rhost.group(1)
            host = rhost.group(4)
        except:
            pass
        try:
            dupe_endpoint = Endpoint.objects.get(
                protocol=protocol,
                host=host,
                query=query,
                fragment=fragment,
                path=path,
            )
        except Endpoint.DoesNotExist:
            dupe_endpoint = None

        if not dupe_endpoint:
            endpoint = Endpoint(
                protocol=protocol,
                host=host,
                query=query,
                fragment=fragment,
                path=path,
            )
        else:
            endpoint = dupe_endpoint

        if not dupe_endpoint:
            endpoints = [endpoint]
        else:
            endpoints = [endpoint, dupe_endpoint]

        finding.unsaved_endpoints = finding.unsaved_endpoints + endpoints
