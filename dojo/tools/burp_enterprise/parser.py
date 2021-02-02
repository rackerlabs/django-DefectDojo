import logging
import re
from urllib.parse import urlparse

from lxml import etree

from dojo.models import Endpoint, Finding

logger = logging.getLogger(__name__)


class BurpEnterpriseHtmlParser(object):
    def get_findings(self, filename, test, mode=None):
        parser = etree.HTMLParser()
        tree = etree.parse(filename, parser)
        if tree:
            return self.get_items(tree, test)
        else:
            return ()

    def get_content(self, container):
        s = ""
        if (
            container.tag == "div"
            and container.text is not None
            and not container.text.isspace()
            and len(container.text) > 0
        ):
            s += (
                "".join(container.itertext())
                .strip()
                .replace("Snip", "\n<-------------- Snip -------------->")
                .replace("\t", "")
            )
        else:
            for elem in container.iterchildren():
                # print(elem.tag, ' : ', elem.text, '\n')
                if elem.text is not None and elem.text.strip() != "":
                    if elem.tag == "a":
                        s += "(" + elem.text + ")[" + elem.attrib["href"] + "]" + "\n"
                    elif elem.tag == "p":
                        s += elem.text + "\n"
                    elif elem.tag == "li":
                        s += "* "
                        if elem.text is not None:
                            s += elem.text + "\n"
                    elif elem.text.isspace():
                        s += list(elem.itertext())[0]
                    elif elem.tag == "div" or elem.tag == "span":
                        s += elem.text.strip() + "\n"
                    else:
                        continue
                else:
                    s += self.get_content(elem)
        return s

    # Get the endpoints and severities associated with each vulnerability
    def pre_allocate_items(self, tree):
        items = list()
        endpoint_text = tree.xpath("/html/body/div/div[contains(@class, 'section')]/h1")
        severities = tree.xpath(
            "/html/body/div/div[contains(@class, 'section')]/table[contains(@class, 'issue-table')]/tbody"
        )
        endpoint_text = [
            endpoint
            for endpoint in endpoint_text
            if ("Issues found" in "".join(endpoint.itertext()).strip())
        ]

        for index in range(0, len(severities)):
            url = endpoint_text[index].text[16:]
            sev_table = list(severities[index].iter("tr"))

            title = ""
            endpoint = ""
            for item in sev_table:
                item_list = list(item.iter("td"))
                if len(item_list) == 1:
                    title_list = item_list[0].text.strip().split(" ")
                    title = " ".join(title_list[:-1])
                else:
                    endpoint = item_list[0].text.strip()
                    severity = item_list[1].text.strip()
                    vuln = dict()
                    vuln["Severity"] = severity
                    vuln["Title"] = title
                    vuln["Description"] = ""
                    vuln["Impact"] = ""
                    vuln["Mitigation"] = ""
                    vuln["References"] = ""
                    vuln["CWE"] = ""
                    vuln["Response"] = ""
                    vuln["Request"] = ""
                    vuln["Endpoint"] = [url + endpoint]
                    vuln["URL"] = url
                    items.append(vuln)
        return items

    def get_items(self, tree, test):
        # Check that there is at least one vulnerability (the vulnerabilities table is absent when no vuln are found)
        vulns = tree.xpath(
            "/html/body/div/div[contains(@class, 'section details')]/div[contains(@class, 'issue-container')]"
        )
        if len(vulns) == 0:
            return list()

        dict_index = 0
        description = ["Issue detail:", "Issue description"]
        reqrsp = ["Request", "Response"]
        impact = ["Issue background", "Issue remediation"]
        mitigation = ["Remediation detail:", "Remediation background"]
        references = ["Vulnerability classifications", "References"]
        vuln = None
        merge = False
        items = self.pre_allocate_items(tree)
        for issue in vulns:
            elems = list(issue.iterchildren())
            curr_vuln = items[dict_index]
            if vuln is None or (
                curr_vuln["Title"] != vuln["Title"] or curr_vuln["URL"] != vuln["URL"]
            ):
                vuln = curr_vuln
                merge = False
            else:
                if curr_vuln["Endpoint"][0] not in vuln["Endpoint"]:
                    vuln_list = vuln["Endpoint"]
                    vuln_list.append(curr_vuln["Endpoint"][0])
                    vuln["Endpoint"] = vuln_list
                merge = True

            for index in range(3, len(elems), 2):
                primary, secondary = elems[index].text.strip(), elems[index + 1]
                field = self.get_content(secondary)
                webinfo = primary.split(":")[0]
                details = "**" + primary + "**\n" + field + "\n\n"
                # Description
                if primary in description:
                    if merge:
                        if field != vuln["Description"].split("\n")[1]:
                            vuln["Description"] = vuln["Description"] + field + "\n\n"
                    else:
                        vuln["Description"] = vuln["Description"] + details
                # Impact
                if primary in impact and not merge:
                    vuln["Impact"] = vuln["Impact"] + details
                # Mitigation
                if primary in mitigation and not merge:
                    vuln["Mitigation"] = vuln["Mitigation"] + details
                # References and CWE
                if primary in references and not merge:
                    if len(vuln["CWE"]) < 1 and field.find("CWE") != -1:
                        vuln["CWE"] += str(self.get_cwe(field))
                    vuln["References"] = vuln["References"] + details
                # Request and Response pairs
                if webinfo in reqrsp:
                    if webinfo == "Request":
                        vuln["Request"] = vuln["Request"] + field + "SPLITTER"
                    else:
                        vuln["Response"] = vuln["Response"] + field + "SPLITTER"

            dict_index += 1

        return list(self.create_findings(items, test))

    def get_cwe(self, vuln_references):
        # Match only the first CWE!
        vuln_references = vuln_references.split(":")[0]
        cweSearch = re.search("CWE-([0-9]*)", vuln_references, re.IGNORECASE)
        if cweSearch:
            return cweSearch.group(1)
        else:
            return 0

    def create_findings(self, items, test):
        # Dictonary to hold the aggregated findings with:
        #  - key: the concatenated aggregate keys
        #  - value: the finding
        dupes = dict()
        for details in items:
            if details.get("Description") == "":
                continue
            aggregateKeys = "{}{}{}{}".format(
                details.get("Title"),
                details.get("Description"),
                details.get("CWE"),
                details.get("Endpoint"),
            )
            find = Finding(
                title=details.get("Title"),
                description=details.get("Description"),
                test=test,
                severity=details.get("Severity"),
                mitigation=details.get("Mitigation"),
                references=details.get("References"),
                impact=details.get("Impact"),
                cwe=int(details.get("CWE")),
                active=False,
                verified=False,
                false_p=False,
                duplicate=False,
                out_of_scope=False,
                mitigated=None,
                numerical_severity=Finding.get_numerical_severity(
                    details.get("Severity")
                ),
                static_finding=False,
                dynamic_finding=True,
                nb_occurences=1,
            )

            if len(details.get("Request")) > 0:
                requests = details.get("Request").split("SPLITTER")[:-1]
                responses = details.get("Response").split("SPLITTER")[:-1]
                unsaved_req_resp = list()
                for index in range(0, len(requests)):
                    unsaved_req_resp.append(
                        {"req": requests[index], "resp": responses[index]}
                    )
                find.unsaved_req_resp = unsaved_req_resp

            find.unsaved_endpoints = list()
            dupes[aggregateKeys] = find

            for url in details.get("Endpoint"):
                parsedUrl = urlparse(url)
                protocol = parsedUrl.scheme
                query = parsedUrl.query
                fragment = parsedUrl.fragment
                path = parsedUrl.path
                port = ""  # Set port to empty string by default
                # Split the returned network address into host and
                try:  # If there is port number attached to host address
                    host, port = parsedUrl.netloc.split(":")
                except:  # there's no port attached to address
                    host = parsedUrl.netloc

                find.unsaved_endpoints.append(
                    Endpoint(
                        host=host,
                        port=port,
                        path=path,
                        protocol=protocol,
                        query=query,
                        fragment=fragment,
                    )
                )

        return list(dupes.values())
