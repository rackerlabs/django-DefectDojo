import logging

# from memory_profiler import profile #Comment out this and profile in defectdojo repo
import html2text
from lxml import etree
from lxml.etree import XMLSyntaxError

from .parser_models import AcunetixScanReport, DefectDojoFinding

SCAN_NODE_TAG_NAME = "Scan"
ACUNETIX_XML_SCAN_IGNORE_NODES = ["Technologies", "Crawler"]
ACUNETIX_XML_REPORTITEM_IGNORE_NODES = ["CVEList", "CVSS", "CVSS3"]


# @profile
def get_root_node(filename):
    """
        This method returns root node.
    :param filename:
    :return:
    """
    try:
        tree = etree.parse(filename, etree.XMLParser(resolve_entities=False))
        return tree.getroot()
    except XMLSyntaxError as xse:
        logging.error(
            "ERROR : error parsing XML file {filename}".format(filename=filename)
        )
        raise xse
    except IOError as ioe:
        logging.error(
            "ERROR : xml file {filename} does't exist.".format(filename=filename)
        )
        raise ioe
    except Exception as e:
        logging.error(
            "ERROR : exception while processing XML file {filename}".format(
                filename=filename
            )
        )
        raise e


# @profile
def get_scan_node(root):
    """
        This method return scan node.
    :param root:
    :return: scan node
    """
    scan_node = root[0]

    if scan_node.tag == SCAN_NODE_TAG_NAME:
        return scan_node
    else:
        error_text = (
            "ERROR: '{scan_node_tag_name}' node must be first "
            "child of root element '{root_tag_name}'.".format(
                scan_node_tag_name=SCAN_NODE_TAG_NAME, root_tag_name=root.tag
            )
        )
        raise Exception(error_text)


# @profile
def get_report_item_references_url(references_node):
    """
        This method fetches report item reference urls.
    :param references_node:
    :return: reference urls
    """
    references_urls = []
    for reference_node in list(references_node):
        for child in list(reference_node):
            if child.tag == "URL":
                references_urls.append(child.text)
    return references_urls


# @profile
def get_cwe_id(cwelist_node):
    """
        Return cwe id number
    :param cwelist_node:
    :return:
    """
    # Assuming CWEList contains only CWE node
    if len(cwelist_node):
        cwe = cwelist_node[0]
        return cwe.text
    else:
        return None


# @profile
def get_scan_report_items_details(report_items_node):
    """
        Return report items.
    :param report_items_node:
    :return: report items
    """
    report_items = []

    if not list(report_items_node):
        logging.info("INFO : Report Items empty.")
    else:
        for report_item_node in list(report_items_node):
            report_item = dict()
            for child in list(report_item_node):
                if child.tag not in ACUNETIX_XML_REPORTITEM_IGNORE_NODES:
                    if child.tag == "References":
                        references_urls = get_report_item_references_url(child)
                        report_item["ReferencesURLs"] = references_urls
                    elif child.tag == "CWEList":
                        cwe_id = get_cwe_id(child)
                        report_item["CWEId"] = cwe_id
                    elif child.tag == "TechnicalDetails":
                        report_item["TechnicalDetails"] = child[0].text
                    else:
                        report_item[child.tag] = child.text

            report_items.append(report_item)
    return report_items


# @profile
def get_scan_details(scan_node):
    """
        Fetches scan details from XML and returns it.
    :param scan_node:
    :return: scan_details
    """
    scan_details = dict()
    for child in list(scan_node):
        if child.tag not in ACUNETIX_XML_SCAN_IGNORE_NODES:
            if child.tag == "ReportItems":
                report_items = get_scan_report_items_details(child)
                scan_details["ReportItems"] = report_items
            else:
                scan_details[child.tag] = child.text

    if scan_details:
        return scan_details
    else:
        error_text = (
            "ERROR: fetching scan details from 'Scan' node. 'Scan' node can't be empty."
        )
        raise Exception(error_text)


# @profile
def get_acunetix_scan_report(filename):
    """
        creates accunetix scan report.
    :param filename:
    :return: acunetix scan report
    """
    root = get_root_node(filename)
    scan_node = get_scan_node(root)
    scan_details = get_scan_details(scan_node)
    acunetix_scan_report = AcunetixScanReport(**scan_details)
    return acunetix_scan_report


# @profile
def get_html2text(html):
    """
        converts html to text
    :param html:
    :return: text
    """
    text_maker = html2text.HTML2Text()
    text_maker.body_width = 0
    return text_maker.handle(html)


# @profile
def get_defectdojo_findings(filename):
    """
        Returns defect dojo findings.
    :param filename:
    :return: defectdojo findings
    """

    acunetix_scan_report = get_acunetix_scan_report(filename)
    defectdojo_findings = []
    for report_item in acunetix_scan_report.ReportItems:
        defectdojo_finding = dict()

        if "Affects" in report_item:
            affects = " ({})".format(report_item["Affects"])
        else:
            affects = ""
        defectdojo_finding["title"] = "{}{}".format(report_item["Name"], affects)
        defectdojo_finding["date"] = acunetix_scan_report.StartTime
        defectdojo_finding["cwe"] = report_item["CWEId"]
        defectdojo_finding["url"] = acunetix_scan_report.StartURL
        defectdojo_finding["severity"] = report_item["Severity"]
        defectdojo_finding["description"] = get_html2text(report_item["Description"])
        if "Details" in report_item and len(report_item["Details"].strip()):
            defectdojo_finding["description"] += "\n**Details:**\n{}\n".format(
                report_item["Details"]
            )
        if "TechnicalDetails" in report_item and len(
            report_item["TechnicalDetails"].strip()
        ):
            defectdojo_finding[
                "description"
            ] += "\n**Technical Details:**\n{}\n".format(
                report_item["TechnicalDetails"]
            )
        defectdojo_finding["mitigation"] = get_html2text(report_item["Recommendation"])
        defectdojo_finding["impact"] = get_html2text(report_item["Impact"])
        defectdojo_finding["references"] = ""
        for ref in report_item["ReferencesURLs"]:
            defectdojo_finding["references"] += "{}\n".format(ref)
        defectdojo_finding["false_p"] = report_item["IsFalsePositive"]

        finding = DefectDojoFinding(**defectdojo_finding)
        defectdojo_findings.append(finding)

    return defectdojo_findings
