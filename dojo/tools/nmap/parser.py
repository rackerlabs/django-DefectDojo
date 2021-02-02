from xml.dom import NamespaceErr

import lxml.etree as le

from dojo.models import Endpoint, Finding

__author__ = "patriknordlen"


class NmapXMLParser(object):
    def get_findings(self, file, test):
        parser = le.XMLParser(resolve_entities=False)
        nmap_scan = le.parse(file, parser)
        root = nmap_scan.getroot()
        dupes = dict()
        if "nmaprun" not in root.tag:
            raise NamespaceErr("This doesn't seem to be a valid Nmap xml file.")

        for host in root.iter("host"):
            host_info = "--- HOST ---\n\n"

            ip = host.find("address[@addrtype='ipv4']").attrib["addr"]
            if ip is not None:
                host_info += "IP Address: %s\n" % ip

            fqdn = (
                host.find("hostnames/hostname[@type='PTR']").attrib["name"]
                if host.find("hostnames/hostname[@type='PTR']") is not None
                else None
            )
            if fqdn is not None:
                host_info += "FQDN: %s\n" % fqdn

            host_info += "\n\n"

            for os in host.iter("os"):
                for os_match in os.iter("osmatch"):
                    if "name" in os_match.attrib:
                        host_info += "Host OS: %s\n" % os_match.attrib["name"]
                    if "accuracy" in os_match.attrib:
                        host_info += "Accuracy: {0}%\n".format(
                            os_match.attrib["accuracy"]
                        )

                host_info += "\n\n"

            for port_element in host.xpath("ports/port[state/@state='open']"):
                port = port_element.attrib["portid"]
                protocol = port_element.attrib["protocol"]

                title = "Open port: %s/%s" % (port, protocol)
                description = host_info
                description += "Port/Protocol: %s/%s\n" % (port, protocol)

                service_info = "\n\n"
                if port_element.find("service") is not None:
                    if "product" in port_element.find("service").attrib:
                        service_info += (
                            "Product: %s\n"
                            % port_element.find("service").attrib["product"]
                        )

                    if "version" in port_element.find("service").attrib:
                        service_info += (
                            "Version: %s\n"
                            % port_element.find("service").attrib["version"]
                        )

                    if "extrainfo" in port_element.find("service").attrib:
                        service_info += (
                            "Extra Info: %s\n"
                            % port_element.find("service").attrib["extrainfo"]
                        )

                    description += service_info

                description += "\n\n"

                severity = "Info"
                dupe_key = port
                if dupe_key in dupes:
                    find = dupes[dupe_key]
                    if description is not None:
                        find.description += description
                else:
                    find = Finding(
                        title=title,
                        test=test,
                        active=False,
                        verified=False,
                        description=description,
                        severity=severity,
                        numerical_severity=Finding.get_numerical_severity(severity),
                    )
                    find.unsaved_endpoints = list()
                    dupes[dupe_key] = find

                find.unsaved_endpoints.append(
                    Endpoint(host=ip, fqdn=fqdn, port=port, protocol=protocol)
                )
        return list(dupes.values())
