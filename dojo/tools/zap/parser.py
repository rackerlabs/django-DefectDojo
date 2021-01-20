
"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import re
import socket
from urllib.parse import urlparse

from defusedxml import ElementTree as ET
from django.utils.html import escape, strip_tags

from dojo.models import Endpoint, Finding


class ZapXmlParser(object):
    """
    The objective of this class is to parse an xml file generated by the zap tool.

    TODO: Handle errors.
    TODO: Test zap output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param zap_xml_filepath A proper xml generated by zap
    """

    def get_findings(self, xml_output, test):

        if xml_output is None:
            return []

        tree = self.parse_xml(xml_output)

        if tree:
            return self.get_items(tree, test)
        else:
            return []

    def parse_xml(self, xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead of
        reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.parse(xml_output)
        except SyntaxError as se:
            raise se

        return tree

    def get_items(self, tree, test):
        """
        @return items A list of Host instances
        """

        items = list()
        for node in tree.findall('site'):
            site = Site(node)
            main_host = Endpoint(host=site.name + (":" + site.port) if site.port is not None else "")
            for item in site.items:
                severity = item.riskdesc.split(' ', 1)[0]
                references = ''
                for ref in item.ref:
                    references += ref + "\n"

                find = Finding(title=item.name,
                               cwe=item.cwe,
                               description=strip_tags(item.desc),
                               test=test,
                               severity=severity,
                               mitigation=strip_tags(item.resolution),
                               references=references,
                               active=False,
                               verified=False,
                               false_p=False,
                               duplicate=False,
                               out_of_scope=False,
                               mitigated=None,
                               impact="No impact provided",
                               numerical_severity=Finding.get_numerical_severity(severity))

                find.unsaved_endpoints = [main_host]
                for i in item.items:
                    parts = urlparse(i['uri'])
                    find.unsaved_endpoints.append(Endpoint(protocol=parts.scheme,
                                                           host=parts.netloc[:500],
                                                           path=parts.path[:500],
                                                           query=parts.query[:1000],
                                                           fragment=parts.fragment[:500],
                                                           product=test.engagement.product))
                items.append(find)
        return items


def get_attrib_from_subnode(xml_node, subnode_xpath_expr, attrib_name):
    """
    Finds a subnode in the item node and the retrieves a value from it

    @return An attribute value
    """
    global ETREE_VERSION
    node = None

    if ETREE_VERSION[0] <= 1 and ETREE_VERSION[1] < 3:

        match_obj = re.search(r"([^\@]+?)\[\@([^=]*?)=\'([^\']*?)\'", subnode_xpath_expr)
        if match_obj is not None:
            node_to_find = match_obj.group(1)
            xpath_attrib = match_obj.group(2)
            xpath_value = match_obj.group(3)
            for node_found in xml_node.findall(node_to_find):
                if node_found.attrib[xpath_attrib] == xpath_value:
                    node = node_found
                    break
        else:
            node = xml_node.find(subnode_xpath_expr)

    else:
        node = xml_node.find(subnode_xpath_expr)

    if node is not None:
        return node.get(attrib_name)

    return None


class Site(object):
    def __init__(self, item_node):
        self.node = item_node
        self.name = self.node.get('name')
        self.host = self.node.get('host')
        self.name = self.node.get('name')
        self.port = self.node.get('port')
        self.items = []
        for alert in self.node.findall('alerts/alertitem'):
            self.items.append(Item(alert))

    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        sub_node = self.node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text

        return None

    def resolve(self, host):
        try:
            return socket.gethostbyname(host)
        except:
            pass
        return host


class Item(object):
    """
    An abstract representation of a Item


    @param item_node A item_node taken from an zap xml tree
    """

    def __init__(self, item_node):
        self.node = item_node

        self.id = self.get_text_from_subnode('pluginid')
        self.name = self.get_text_from_subnode('alert')

        self.severity = self.get_text_from_subnode('riskcode')
        self.riskdesc = self.get_text_from_subnode('riskdesc')
        self.desc = self.get_text_from_subnode('desc')
        self.resolution = self.get_text_from_subnode('solution') if self.get_text_from_subnode('solution') else ""
        self.desc += "\n\nReference: " + self.get_text_from_subnode('reference') if self.get_text_from_subnode(
            'reference') else ""
        self.ref = []
        if self.get_text_from_subnode('cweid'):
            self.ref.append("CWE-" + self.get_text_from_subnode('cweid'))
            self.cwe = self.get_text_from_subnode('cweid')
        else:
            self.cwe = 0

        description_detail = "\n"
        for instance in item_node.findall('instances/instance'):
            for node in instance.getiterator():
                # print('tag: ' + node.tag)
                # print('text:' + escape(node.text))
                if node.tag == "uri":
                    if node.text != "":
                        description_detail += "URL: " + node.text
                if node.tag == "method":
                    if node.text != "":
                        description_detail += "Method: " + node.text
                if node.tag == "param":
                    if node.text != "":
                        description_detail += "Parameter: " + node.text
                if node.tag == "evidence":
                    if node.text != "":
                        description_detail += "Evidence: " + escape(node.text)
                description_detail += "\n"

        self.desc += description_detail

        if self.get_text_from_subnode('wascid'):
            self.ref.append("WASC-" + self.get_text_from_subnode('wascid'))

        self.items = []
        i = 0

        for n in item_node.findall('instances/instance/uri'):
            n2 = None
            if item_node.findall('instances/instance/param'):
                n2 = item_node.findall('instances/instance/param')[i]

            # mregex = re.search(
            #     "(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
            #     n.text)

            # protocol = mregex.group(1)
            # host = mregex.group(4)

            protocol = urlparse(n.text).scheme
            host = urlparse(n.text).netloc

            port = 80
            if protocol == 'https':
                port = 443
            # if mregex.group(11) is not None:
            #     port = mregex.group(11)
            if urlparse(n.text).port is not None:
                port = urlparse(n.text).port

            item = {'uri': n.text, 'param': n2.text if n2 else "", 'host': host, 'protocol': protocol, 'port': port}
            self.items.append(item)
            i = i + 1
        self.requests = "\n".join([i['uri'] for i in self.items])

    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        sub_node = self.node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text

        return None


register_parser("ZAP Scan", ZapXmlParser())
