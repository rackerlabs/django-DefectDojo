from lxml import etree
from lxml.etree import XMLSyntaxError
import logging

SCAN_NODE_TAG_NAME = "Scan"


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


def validate_acunetix_scan_xml_file(filename):

    root = get_root_node(filename)
    required_nodes = [
        "Name",
        "ShortName",
        "StartURL",
        "StartTime",
        "FinishTime",
        "ScanTime",
        "Aborted",
        "Responsive",
        "Banner",
        "Os",
        "WebServer",
        "ReportItems",
    ]

    if root.tag != "ScanGroup":
        raise Exception(
            "ERROR : 'root' tag must be 'ScanGroup'. Invalid Acunetix Scan XML file."
        )

    scan_node = get_scan_node(root)
    children = list(scan_node)
    if not children:
        raise Exception(
            "ERROR : 'scan' children shouldn't be empty.Invalid Acunetix Scan XML file."
        )
    else:
        child_tags = []
        for child in children:
            child_tags.append(child.tag)

        if not set(required_nodes).issubset(child_tags):
            raise Exception(
                "ERROR : nodes : {required_nodes} "
                "must be children of 'scan' node.Invalid Acunetix Scan XML file.".format(
                    required_nodes=required_nodes
                )
            )

    print(
        (
            "Acunetix Scan XML file '{filename}' is valid. It can be uploaded to DefectDojo.".format(
                filename=filename
            )
        )
    )


if __name__ == "__main__":
    # filename = "acunetix_valid_dummy.xml"
    filename = "acunetix_invalid_xml_file.xml"
    validate_acunetix_scan_xml_file(filename)
