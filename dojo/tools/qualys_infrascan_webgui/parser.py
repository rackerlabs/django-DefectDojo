#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = "Dennis Van Elst"

# This plugin ports the default Qualys scanner XML output that is generated through the Qualys WebGUI to DefectDojo
# It is essentially a rewrite of the default DefectDojo Qualys import plugin,
# which was developed by John Kim and sponsored by Securicon, LLC.

import argparse
import csv
import logging

from dojo.models import Endpoint, Finding

logger = logging.getLogger(__name__)

# Non-standard libraries
try:
    from lxml import etree
except ImportError:
    logger.debug(
        "Missing lxml library. Please install using PIP. https://pypi.python.org/pypi/lxml/3.4.2"
    )

try:
    import html2text
except ImportError:
    logger.debug(
        "Missing html2text library. Please install using PIP. https://pypi.python.org/pypi/html2text/2015.2.18"
    )

# Custom libraries
try:
    from . import utfdictcsv
except ImportError:
    logger.debug(
        "Missing dict to csv converter custom library. utfdictcsv.py should be in the same path as this file."
    )


def htmltext(blob):
    h = html2text.HTML2Text()
    h.ignore_links = False
    return h.handle(blob)


def report_writer(report_dic, output_filename):
    with open(output_filename, "wb") as outFile:
        csvWriter = utfdictcsv.DictUnicodeWriter(
            outFile, REPORT_HEADERS, quoting=csv.QUOTE_ALL
        )
        csvWriter.writerow(CUSTOM_HEADERS)
        csvWriter.writerows(report_dic)
    logger.debug("Successfully parsed.")


def issue_r(raw_row, vuln, scan_date):
    ret_rows = []
    issue_row = {}

    # IP ADDRESS
    issue_row["ip_address"] = raw_row.get("value")

    # FQDN
    issue_row["fqdn"] = raw_row.get("name")

    # Create Endpoint
    if issue_row["fqdn"]:
        ep = Endpoint(host=issue_row["fqdn"])
    else:
        ep = Endpoint(host=issue_row["ip_address"])

    # OS NAME
    issue_row["os"] = raw_row.findtext("OS")

    # Scan details - VULNS//VULN indicates we only care about confirmed vulnerabilities
    for vuln_details in raw_row.iterfind("VULNS//VULN"):
        _temp = issue_row

        # Port
        _gid = vuln_details.get("number")

        _port = vuln_details.getparent().get("port")
        _temp["port_status"] = _port

        _category = str(vuln_details.getparent().get("value"))

        _result = str(vuln_details.findtext("RESULT"))

        _first_found = str(scan_date)  # Beware: First/Last found not working properly
        _last_found = str(scan_date)
        _times_found = "1"

        finding = Finding()

        # Vuln name
        _temp["vuln_name"] = vuln_details.findtext("TITLE")

        # Vuln Description
        _description = str(vuln_details.findtext("DIAGNOSIS"))
        # Solution Strips Heading Workaround(s)
        _temp["solution"] = htmltext(vuln_details.findtext("SOLUTION"))

        # Vuln_description
        _temp["vuln_description"] = "\n".join(
            [
                htmltext(_description),
                htmltext("Category: " + _category),
                htmltext("QID: " + str(_gid)),
                htmltext("Port: " + str(_port)),
                htmltext("Result Evidence: " + _result),
                htmltext("First Found: " + _first_found),
                htmltext("Last Found: " + _last_found),
                htmltext("Times Found: " + _times_found),
            ]
        )
        # Impact description
        _temp["IMPACT"] = htmltext(vuln_details.findtext("CONSEQUENCE"))

        # CVSS
        _temp["CVSS_score"] = vuln_details.findtext("CVSS_BASE")

        # CVE and LINKS
        _temp_cve_details = vuln_details.iterfind("CVE_ID_LIST/CVE_ID")
        if _temp_cve_details:
            _cl = {
                cve_detail.findtext("ID"): cve_detail.findtext("URL")
                for cve_detail in _temp_cve_details
            }
            _temp["cve"] = "\n".join(list(_cl.keys()))
            _temp["links"] = "\n".join(list(_cl.values()))

        # The CVE in Qualys report might not have a CVSS score, so findings are informational by default
        # unless we can find map to a Severity OR a CVSS score from the findings detail.
        sev = None
        if _temp["CVSS_score"] is not None and float(_temp["CVSS_score"]) > 0:
            if 0.1 <= float(_temp["CVSS_score"]) <= 3.9:
                sev = "Low"
            elif 4.0 <= float(_temp["CVSS_score"]) <= 6.9:
                sev = "Medium"
            elif 7.0 <= float(_temp["CVSS_score"]) <= 8.9:
                sev = "High"
            elif float(_temp["CVSS_score"]) >= 9.0:
                sev = "Critical"
        elif vuln_details.get("severity") is not None:
            if int(vuln_details.get("severity")) == 1:
                sev = "Informational"
            elif int(vuln_details.get("severity")) == 2:
                sev = "Low"
            elif int(vuln_details.get("severity")) == 3:
                sev = "Medium"
            elif int(vuln_details.get("severity")) == 4:
                sev = "High"
            elif int(vuln_details.get("severity")) == 5:
                sev = "Critical"
        elif sev is None:
            sev = "Informational"
        finding = None
        if _temp_cve_details:
            refs = "\n".join(list(_cl.values()))
            finding = Finding(
                title=_temp["vuln_name"],
                mitigation=_temp["solution"],
                description=_temp["vuln_description"],
                severity=sev,
                references=refs,
                impact=_temp["IMPACT"],
            )

        else:
            finding = Finding(
                title=_temp["vuln_name"],
                mitigation=_temp["solution"],
                description=_temp["vuln_description"],
                severity=sev,
                references=_gid,
                impact=_temp["IMPACT"],
            )
        finding.unsaved_endpoints = list()
        finding.unsaved_endpoints.append(ep)
        ret_rows.append(finding)
    return ret_rows


def qualys_infrascan_parser(qualys_xml_file):
    master_list = []
    if qualys_xml_file is not None:
        parser = etree.XMLParser(
            resolve_entities=False,
            remove_blank_text=True,
            no_network=True,
            recover=True,
        )
        d = etree.parse(qualys_xml_file, parser)

        # fetch scan date e.g.: <KEY value="DATE">2020-01-30T09:45:41Z</KEY>
        scan_date = ""
        header = d.xpath("/SCAN/HEADER/KEY")
        for i in header:
            if i.get("value") == "DATE":
                scan_date = i.text

        r = d.xpath("/SCAN/IP")

        for issue in r:
            master_list += issue_r(issue, d, scan_date)
    return master_list
    # report_writer(master_list, args.outfile)


if __name__ == "__main__":
    # Parse args
    aparser = argparse.ArgumentParser(
        description="Converts Qualys XML results to .csv file."
    )
    aparser.add_argument(
        "--out",
        dest="outfile",
        default="qualys.csv",
        help="WARNING: By default, output will overwrite current path to the file named 'qualys.csv'",
    )

    aparser.add_argument("qualys_xml_file", type=str, help="Qualys xml file.")

    args = aparser.parse_args()

    try:
        qualys_parser(args.qualys_xml_file)
    except IOError:
        logger.error("[!] Error processing file: {}".format(args.qualys_xml_file))
        exit()


# still need to import this in Dojo
class QualysInfraScanParser(object):
    def get_findings(self, file, test):
        return qualys_infrascan_parser(file)
