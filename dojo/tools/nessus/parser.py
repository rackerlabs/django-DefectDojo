import csv
import io
import logging
import re
import sys
from xml.dom import NamespaceErr

from cpe import CPE
from cvss import CVSS3
from defusedxml import ElementTree

from dojo.models import Endpoint, Finding, Test

LOGGER = logging.getLogger(__name__)


class NessusCSVParser(object):
    def _convert_severity(self, val):
        if "None" == val:
            return "Info"
        if val is None:
            return "Info"
        else:
            return val.title()

    def _format_cve(self, val):
        if val is None:
            return None
        elif "" == val:
            return None
        cve_match = re.findall(r"CVE-[0-9]+-[0-9]+", val.upper(), re.IGNORECASE)
        if cve_match:
            return cve_match
        return None

    def _format_cpe(self, val):
        if val is None:
            return None
        elif "" == val:
            return None
        cpe_match = re.findall(r"cpe:/[^\n\ ]+", val)
        if cpe_match:
            return cpe_match
        return None

    def get_findings(self, filename, test: Test):
        content = filename.read()
        if type(content) is bytes:
            content = content.decode("utf-8")
        csv.field_size_limit(int(sys.maxsize / 10))  # the request/resp are big
        reader = csv.DictReader(io.StringIO(content))
        dupes = dict()
        for row in reader:
            # manage severity from two possible columns 'Severity' and 'Risk'
            severity = "Info"
            if "Severity" in row:
                severity = self._convert_severity(row.get("Severity"))
            elif "Risk" in row:
                severity = self._convert_severity(row.get("Risk"))
            # manage title from two possible columns 'Nme' and 'Plugin Name'
            title = row.get("Name")
            if title is None and "Plugin Name" in row:
                title = row.get("Plugin Name")
            # special case to skip empty titles
            if not title:
                continue
            description = row.get("Synopsis")
            mitigation = str(row.get("Solution"))
            impact = row.get("Description", "N/A")
            references = row.get("See Also", "N/A")

            dupe_key = (
                severity
                + title
                + row.get("Host", "No host")
                + str(row.get("Port", "No port"))
                + row.get("Synopsis", "No synopsis")
            )

            detected_cve = self._format_cve(str(row.get("CVE")))
            cve = None
            if detected_cve:
                # FIXME support more than one CVE in Nessus CSV parser
                cve = detected_cve[0]
                if len(detected_cve) > 1:
                    LOGGER.warning(
                        "more than one CVE for a finding. NOT supported by Nessus CSV parser"
                    )

            if dupe_key in dupes:
                find = dupes[dupe_key]
                if "Plugin Output" in row:
                    find.description += row.get("Plugin Output")
            else:
                if "Plugin Output" in row:
                    description = description + str(row.get("Plugin Output"))
                find = Finding(
                    title=title,
                    test=test,
                    active=False,
                    cve=cve,
                    verified=False,
                    description=description,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                )

                # manage CVSS vector (only v3.x for now)
                if "CVSS V3 Vector" in row and "" != row.get("CVSS V3 Vector"):
                    find.cvssv3 = CVSS3(
                        "CVSS:3.0/" + str(row.get("CVSS V3 Vector"))
                    ).clean_vector(output_prefix=False)
                # manage CPE data
                detected_cpe = self._format_cpe(str(row.get("CPE")))
                if detected_cpe:
                    # FIXME support more than one CPE in Nessus CSV parser
                    if len(detected_cpe) > 1:
                        LOGGER.warning(
                            "more than one CPE for a finding. NOT supported by Nessus CSV parser"
                        )
                    cpe_decoded = CPE(detected_cpe[0])
                    find.component_name = (
                        cpe_decoded.get_product()[0]
                        if len(cpe_decoded.get_product()) > 0
                        else None
                    )
                    find.component_version = (
                        cpe_decoded.get_version()[0]
                        if len(cpe_decoded.get_version()) > 0
                        else None
                    )

                find.unsaved_endpoints = list()
                dupes[dupe_key] = find
            # manage endpoints
            endpoint = Endpoint(host="localhost")
            if "Host" in row:
                endpoint.host = row.get("Host")
            elif "IP Address" in row:
                endpoint.host = row.get("IP Address")
            endpoint.port = row.get("Port")
            if "Protocol" in row:
                endpoint.protocol = row.get("Protocol").lower()
            find.unsaved_endpoints.append(endpoint)
        return list(dupes.values())


class NessusXMLParser(object):
    def get_findings(self, file, test):
        nscan = ElementTree.parse(file)
        root = nscan.getroot()

        if "NessusClientData_v2" not in root.tag:
            raise NamespaceErr(
                "This version of Nessus report is not supported. Please make sure the export is "
                "formatted using the NessusClientData_v2 schema."
            )
        dupes = {}
        for report in root.iter("Report"):
            for host in report.iter("ReportHost"):
                ip = host.attrib["name"]
                fqdn = (
                    host.find(".//HostProperties/tag[@name='host-fqdn']").text
                    if host.find(".//HostProperties/tag[@name='host-fqdn']") is not None
                    else None
                )

                for item in host.iter("ReportItem"):
                    # if item.attrib["svc_name"] == "general":
                    #     continue

                    port = None
                    if float(item.attrib["port"]) > 0:
                        port = item.attrib["port"]

                    protocol = None
                    if str(item.attrib["protocol"]):
                        protocol = item.attrib["protocol"]

                    description = ""
                    plugin_output = None
                    if item.findtext("synopsis"):
                        description = item.find("synopsis").text + "\n\n"
                    if item.findtext("plugin_output"):
                        plugin_output = (
                            "Plugin Output: "
                            + ip
                            + ((":" + port) if port is not None else "")
                            + " \n```\n"
                            + item.find("plugin_output").text
                            + "\n```\n\n"
                        )
                        description += plugin_output

                    nessus_severity_id = int(item.attrib["severity"])
                    severity = self.get_text_severity(nessus_severity_id)

                    impact = ""
                    if item.find("description"):
                        impact = item.find("description").text + "\n\n"
                    if item.findtext("cvss_vector"):
                        impact += "CVSS Vector: " + item.find("cvss_vector").text + "\n"
                    if item.findtext("cvss_base_score"):
                        impact += (
                            "CVSS Base Score: "
                            + item.find("cvss_base_score").text
                            + "\n"
                        )
                    if item.findtext("cvss_temporal_score"):
                        impact += (
                            "CVSS Temporal Score: "
                            + item.find("cvss_temporal_score").text
                            + "\n"
                        )

                    mitigation = (
                        item.find("solution").text
                        if item.find("solution") is not None
                        else "N/A"
                    )
                    references = ""
                    for ref in item.iter("see_also"):
                        refs = ref.text.split()
                        for r in refs:
                            references += r + "\n"

                    for xref in item.iter("xref"):
                        references += xref.text + "\n"

                    cve = None
                    if item.findtext("cve"):
                        cve = item.find("cve").text
                    cwe = None
                    if item.findtext("cwe"):
                        cwe = item.find("cwe").text
                    title = item.attrib["pluginName"]
                    dupe_key = severity + title

                    if dupe_key in dupes:
                        find = dupes[dupe_key]
                        if plugin_output is not None:
                            find.description += plugin_output
                    else:
                        find = Finding(
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
                            cwe=cwe,
                            cve=cve,
                        )
                        find.unsaved_endpoints = list()
                        dupes[dupe_key] = find

                    find.unsaved_endpoints.append(
                        Endpoint(
                            host=ip + (":" + port if port is not None else ""),
                            protocol=protocol,
                        )
                    )
                    if fqdn is not None:
                        find.unsaved_endpoints.append(
                            Endpoint(host=fqdn, protocol=protocol)
                        )

        return list(dupes.values())

    def get_text_severity(self, severity_id):
        """Convert data of the report into severity"""
        if severity_id == 4:
            return "Critical"
        elif severity_id == 3:
            return "High"
        elif severity_id == 2:
            return "Medium"
        elif severity_id == 1:
            return "Low"
        else:
            return "Info"


class NessusParser(object):
    def get_findings(self, filename, test):

        if filename.name.lower().endswith(".xml"):
            return list(NessusXMLParser().parse(filename, test).values())
        elif filename.name.lower().endswith(".csv"):
            return list(NessusCSVParser().parse(filename, test).values())
        else:
            raise ValueError("Unknown File Format")
