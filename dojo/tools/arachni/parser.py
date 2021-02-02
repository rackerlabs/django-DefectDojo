import json
from base64 import b64encode
from urllib.parse import urlparse

import html2text
from django.utils.encoding import force_str

from dojo.models import Endpoint, Finding


class ArachniJSONParser(object):
    def get_findings(self, json_output, test):
        self.target = None
        self.port = "80"
        self.host = None

        tree = self.parse_json(json_output)
        if tree:
            return [data for data in self.get_items(tree, test)]
        else:
            return []

    def parse_json(self, json_output):
        try:
            data = json_output.read()
            try:
                tree = json.loads(str(data, "utf-8"))
            except:
                tree = json.loads(data)
        except:
            raise Exception("Invalid format")

        return tree

    def get_items(self, tree, test):
        bugtype = ""
        items = {}

        issues = tree["issues"]

        for node in issues:
            item = get_item(node, test)
            dupe_key = str(item.url) + item.severity + item.title
            if dupe_key in items:
                items[dupe_key].unsaved_endpoints = (
                    items[dupe_key].unsaved_endpoints + item.unsaved_endpoints
                )
                items[dupe_key].unsaved_req_resp = (
                    items[dupe_key].unsaved_req_resp + item.unsaved_req_resp
                )

                # make sure only unique endpoints are retained
                unique_objs = []
                new_list = []
                for o in items[dupe_key].unsaved_endpoints:
                    if o.__unicode__() in unique_objs:
                        continue
                    new_list.append(o)
                    unique_objs.append(o.__unicode__())

                items[dupe_key].unsaved_endpoints = new_list
            else:
                items[dupe_key] = item

        return list(items.values())


def do_clean(value):
    myreturn = ""
    if value is not None:
        if len(value) > 0:
            for x in value:
                myreturn += x.text
    return myreturn


def get_item(item_node, test):
    if "vector" in item_node and "action" in item_node["vector"]:
        url = item_node["vector"]["action"]
    else:
        url = item_node["response"]["url"]

    o = urlparse(url)

    """

    ParseResult(scheme='http', netloc='www.cwi.nl:80', path='/%7Eguido/Python.html',
                params='', query='', fragment='')
    """

    # rhost = re.search(
    #     "(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
    #     url)
    protocol = o.scheme
    host = o.netloc
    path = o.path
    query = o.query
    fragment = o.fragment

    port = 80
    if protocol == "https":
        port = 443

    # if rhost.group(11) is not None:
    #     port = rhost.group(11)
    if o.port is not None:
        port = o.port

    request = item_node["request"]
    #
    req = ""
    #
    for key, value in request.items():
        req += str(key) + ": " + str(value) + "\n\n"
    #
    respz = item_node["response"]

    resp = ""

    for key, value in respz.items():
        if key != "body":
            resp += str(key) + ": " + str(value) + "\n\n"

    resp += "\n\n\n" + force_str(respz["body"])
    unsaved_req_resp = list()

    if request is not None and respz is not None:
        unsaved_req_resp.append(
            {
                "req": b64encode(req.encode("utf-8")),
                "resp": b64encode(resp.encode("utf-8")),
            }
        )

    try:
        dupe_endpoint = Endpoint.objects.get(
            protocol=protocol,
            host=host + (":" + port) if port is not None else "",
            query=query,
            fragment=fragment,
            path=path,
            product=test.engagement.product,
        )
    except:
        dupe_endpoint = None

    if not dupe_endpoint:
        endpoint = Endpoint(
            protocol=protocol,
            host=host + (":" + str(port)) if port is not None else "",
            query=query,
            fragment=fragment,
            path=path,
            product=test.engagement.product,
        )
    else:
        endpoint = dupe_endpoint

    if not dupe_endpoint:
        endpoints = [endpoint]
    else:
        endpoints = [endpoint, dupe_endpoint]

    background = item_node["description"] if "description" in item_node else None
    if background:
        background = html2text.html2text(background)

    remediation = (
        item_node["remedy_guidance"] if "remedy_guidance" in item_node else "n/a"
    )
    if remediation:
        remediation = html2text.html2text(remediation)

    references = (
        list(item_node["references"].values()) if "references" in item_node else None
    )
    references = "<br/><br/>".join(reference for reference in references)

    if references:
        references = html2text.html2text(references)

    severity = item_node["severity"].capitalize() if "severity" in item_node else "Info"

    if severity == "Informational":
        severity == "Info"

    cwe = item_node["cwe"] if "cwe" in item_node else None

    tags = item_node["tags"] if "tags" in item_node else None

    if tags:
        tags = ", ".join(tag for tag in tags)

    digest = item_node["digest"]
    # Finding and Endpoint objects returned have not been saved to the database
    finding = Finding(
        title=item_node["name"] + " (" + str(digest) + ")",
        url=url,
        test=test,
        severity=severity,
        description=background + "\n\n",
        mitigation=remediation,
        references=references,
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        impact="No impact provided",
        numerical_severity=Finding.get_numerical_severity(severity),
        cwe=cwe,
    )
    finding.unsaved_endpoints = endpoints
    finding.unsaved_req_resp = unsaved_req_resp
    finding.unsaved_tags = tags

    return finding
