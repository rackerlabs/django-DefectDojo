import datetime
import logging
import html2text
from defusedxml import ElementTree as etree
from cvss import CVSS3

from dojo.models import Endpoint, Finding
from dojo.tools.qualys import csv_parser

logger = logging.getLogger(__name__)


CUSTOM_HEADERS = {'CVSS_score': 'CVSS Score',
                  'ip_address': 'IP Address',
                  'fqdn': 'FQDN',
                  'os': 'OS',
                  'port_status': 'Port',
                  'vuln_name': 'Vulnerability',
                  'vuln_description': 'Description',
                  'solution': 'Solution',
                  'links': 'Links',
                  'cve': 'CVE',
                  'vuln_severity': 'Severity',
                  'QID': 'QID',
                  'first_found': 'First Found',
                  'last_found': 'Last Found',
                  'found_times': 'Found Times',
                  'category': 'Category'
                  }

REPORT_HEADERS = ['CVSS_score',
                  'ip_address',
                  'fqdn',
                  'os',
                  'port_status',
                  'vuln_name',
                  'vuln_description',
                  'solution',
                  'links',
                  'cve',
                  'Severity',
                  'QID',
                  'first_found',
                  'last_found',
                  'found_times',
                  'category',
                  ]


def htmltext(blob):
    h = html2text.HTML2Text()
    h.ignore_links = False
    return h.handle(blob)


def split_cvss(value, _temp):
    # Check if CVSS field contains the CVSS vector
    if value is None or len(value) == 0 or value == "-":
        return
    if len(value) > 4:
        split = value.split(" (")
        _temp['CVSS_value'] = float(split[0])
        # remove ")" at the end
        _temp['CVSS_vector'] = CVSS3("CVSS:3.0/" + split[1][:-1]).clean_vector()
    else:
        _temp['CVSS_value'] = float(value)


def parse_finding(host, tree):
    ret_rows = []
    issue_row = {}

    # IP ADDRESS
    issue_row['ip_address'] = host.findtext('IP')

    # FQDN
    issue_row['fqdn'] = host.findtext('DNS')

    # Create Endpoint
    if issue_row['fqdn']:
        ep = Endpoint(host=issue_row['fqdn'])
    else:
        ep = Endpoint(host=issue_row['ip_address'])

    # OS NAME
    issue_row['os'] = host.findtext('OPERATING_SYSTEM')

    # Scan details
    for vuln_details in host.iterfind('VULN_INFO_LIST/VULN_INFO'):
        _temp = issue_row
        # Port
        _gid = vuln_details.find('QID').attrib['id']
        _port = vuln_details.findtext('PORT')
        _temp['port_status'] = _port

        _category = str(vuln_details.findtext('CATEGORY'))
        _result = str(vuln_details.findtext('RESULT'))
        _first_found = str(vuln_details.findtext('FIRST_FOUND'))
        _last_found = str(vuln_details.findtext('LAST_FOUND'))
        _times_found = str(vuln_details.findtext('TIMES_FOUND'))

        _temp['date'] = datetime.datetime.strptime(vuln_details.findtext('LAST_FOUND'), "%Y-%m-%dT%H:%M:%SZ").date()
        # Vuln_status
        status = vuln_details.findtext('VULN_STATUS')
        if status == "Active" or status == "Re-Opened" or status == "New":
            _temp['active'] = True
            _temp['mitigated'] = False
            _temp['mitigation_date'] = None
        else:
            _temp['active'] = False
            _temp['mitigated'] = True
            last_fixed = vuln_details.findtext('LAST_FIXED')
            if last_fixed is not None:
                _temp['mitigation_date'] = datetime.datetime.strptime(last_fixed, "%Y-%m-%dT%H:%M:%SZ").date()
            else:
                _temp['mitigation_date'] = None
        # read cvss value if present
        cvss3 = vuln_details.findtext('CVSS3_FINAL')
        if cvss3 is not None and cvss3 != "-":
            split_cvss(cvss3, _temp)
        else:
            cvss2 = vuln_details.findtext('CVSS_FINAL')
            if cvss2 is not None and cvss2 != "-":
                split_cvss(cvss2, _temp)
                # DefectDojo does not support cvssv2
                _temp['CVSS_vector'] = None

        search = ".//GLOSSARY/VULN_DETAILS_LIST/VULN_DETAILS[@id='{}']".format(_gid)
        vuln_item = tree.find(search)
        if vuln_item is not None:
            finding = Finding()
            # Vuln name
            _temp['vuln_name'] = vuln_item.findtext('TITLE')

            # Vuln Description
            _description = str(vuln_item.findtext('THREAT'))
            # Solution Strips Heading Workaround(s)
            # _temp['solution'] = re.sub('Workaround(s)?:.+\n', '', htmltext(vuln_item.findtext('SOLUTION')))
            _temp['solution'] = htmltext(vuln_item.findtext('SOLUTION'))

            # Vuln_description
            _temp['vuln_description'] = "\n".join([htmltext(_description),
                                                   htmltext("Category: " + _category),
                                                   htmltext("QID: " + str(_gid)),
                                                   htmltext("Port: " + str(_port)),
                                                   htmltext("Result Evidence: " + _result),
                                                   htmltext("First Found: " + _first_found),
                                                   htmltext("Last Found: " + _last_found),
                                                   htmltext("Times Found: " + _times_found),
                                                   ])
            # Impact description
            _temp['IMPACT'] = htmltext(vuln_item.findtext('IMPACT'))

            # read cvss value if present and not already read from vuln
            if _temp.get('CVSS_value') is None:
                cvss3 = vuln_item.findtext('CVSS3_SCORE/CVSS3_BASE')
                cvss2 = vuln_item.findtext('CVSS_SCORE/CVSS_BASE')
                if cvss3 is not None and cvss3 != "-":
                    split_cvss(cvss3, _temp)
                else:
                    cvss2 = vuln_item.findtext('CVSS_FINAL')
                    if cvss2 is not None and cvss2 != "-":
                        split_cvss(cvss2, _temp)
                        # DefectDojo does not support cvssv2
                        _temp['CVSS_vector'] = None

            # CVE and LINKS
            _temp_cve_details = vuln_item.iterfind('CVE_ID_LIST/CVE_ID')
            if _temp_cve_details:
                _cl = {cve_detail.findtext('ID'): cve_detail.findtext('URL') for cve_detail in _temp_cve_details}
                _temp['cve'] = "\n".join(list(_cl.keys()))
                _temp['links'] = "\n".join(list(_cl.values()))
        # The CVE in Qualys report might not have a CVSS score, so findings are informational by default
        # unless we can find map to a Severity OR a CVSS score from the findings detail.
        sev = None
        if _temp.get('CVSS_value') is not None and _temp['CVSS_value'] > 0:
            if 0.1 <= float(_temp['CVSS_value']) <= 3.9:
                sev = 'Low'
            elif 4.0 <= float(_temp['CVSS_value']) <= 6.9:
                sev = 'Medium'
            elif 7.0 <= float(_temp['CVSS_value']) <= 8.9:
                sev = 'High'
            elif float(_temp['CVSS_value']) >= 9.0:
                sev = 'Critical'
        elif vuln_item.findtext('SEVERITY') is not None:
            if int(vuln_item.findtext('SEVERITY')) == 1:
                sev = 'Informational'
            elif int(vuln_item.findtext('SEVERITY')) == 2:
                sev = 'Low'
            elif int(vuln_item.findtext('SEVERITY')) == 3:
                sev = 'Medium'
            elif int(vuln_item.findtext('SEVERITY')) == 4:
                sev = 'High'
            elif int(vuln_item.findtext('SEVERITY')) == 5:
                sev = 'Critical'
        elif sev is None:
            sev = 'Informational'
        finding = None
        if _temp_cve_details:
            refs = "\n".join(list(_cl.values()))
            finding = Finding(title="QID-" + _gid[4:] + " | " + _temp['vuln_name'],
                              mitigation=_temp['solution'],
                              description=_temp['vuln_description'],
                              severity=sev,
                              references=refs,
                              impact=_temp['IMPACT'],
                              date=_temp['date'],
                              vuln_id_from_tool=_gid,
                              )

        else:
            finding = Finding(title="QID-" + _gid[4:] + " | " + _temp['vuln_name'],
                              mitigation=_temp['solution'],
                              description=_temp['vuln_description'],
                              severity=sev,
                              references=_gid,
                              impact=_temp['IMPACT'],
                              date=_temp['date'],
                              vuln_id_from_tool=_gid,
                              )
        finding.mitigated = _temp['mitigation_date']
        finding.is_mitigated = _temp['mitigated']
        finding.active = _temp['active']
        if _temp.get('CVSS_vector') is not None:
            finding.cvssv3 = _temp.get('CVSS_vector')
        finding.verified = True
        finding.unsaved_endpoints = list()
        finding.unsaved_endpoints.append(ep)
        ret_rows.append(finding)
    return ret_rows


def qualys_parser(qualys_xml_file):
    parser = etree.XMLParser()
    tree = etree.parse(qualys_xml_file, parser)
    host_list = tree.find('HOST_LIST')
    finding_list = []
    if host_list is not None:
        for host in host_list:
            finding_list += parse_finding(host, tree)
    return finding_list


class QualysParser(object):

    def get_scan_types(self):
        return ["Qualys Scan"]

    def get_label_for_scan_types(self, scan_type):
        return "Qualys Scan"

    def get_description_for_scan_types(self, scan_type):
        return "Qualys WebGUI output files can be imported in XML format."

    def get_findings(self, file, test):
        if file.name.lower().endswith('.csv'):
            return csv_parser.parse_csv(file)
        else:
            return qualys_parser(file)
