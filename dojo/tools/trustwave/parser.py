# Based on CSV, but rewrote because
# values in different columns required concatinaton

import csv
import hashlib
import io
import re
import socket
from urllib.parse import urlparse

from dojo.models import Endpoint, Finding

MAPPINGS = {
    "title": "Vulnerability Name",
    "description": "Description",
    "protocol": "Port",
    "references": "Evidence",
    "mitigation": "Remediation",
    "cwe": "CVE",
    "fqdn": "Domain",
    "severity": "Severity",
    "ip": "IP",
}


class Urlfilter:
    def __init__(self):
        self.host = ""
        self.path = ""
        self.query = ""
        self.fragment = ""
        self.url = ""
        self.validip = False

    def is_valid_ipv4_address(self, address):
        valid = True
        try:
            socket.inet_aton(address.strip())
        except:
            valid = False

        return valid

    def eval_column(self, column_value):
        url = column_value
        self.url = url
        o = urlparse(url)

        """
        Todo: Replace this with a centralized parsing function as many of the parsers
        use the same method for parsing urls.

        ParseResult(scheme='http', netloc='www.cwi.nl:80', path='/%7Eguido/Python.html',
                    params='', query='', fragment='')
        """
        if self.is_valid_ipv4_address(url) is False:
            rhost = re.search(
                r"(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
                url,
            )
            if rhost:
                self.host = o.netloc
                self.path = o.path
                self.query = o.query
                self.fragment = o.fragment
                self.validip = False

        # URL is an IP so save as an IP endpoint
        elif self.is_valid_ipv4_address(url) is True:
            self.host = url
            self.path = None
            self.query = None
            self.fragment = None
            self.validip = True


class Severityfilter:
    def __init__(self):
        self.severity_mapping = {
            "I": "Info",
            "L": "Low",
            "M": "Medium",
            "H": "High",
            "C": "Critical",
        }
        self.severity = None

    def eval_column(self, column_value):
        if column_value in list(self.severity_mapping.keys()):
            self.severity = self.severity_mapping[column_value]
        else:
            self.severity = "Info"


class TrustwaveUploadCsvParser(object):
    def get_findings(self, filename, test):
        self.dupes = dict()
        self.items = ()

        if filename is None:
            self.items = ()
            return

        content = filename.read()
        reader = csv.DictReader(io.StringIO(content), delimiter=",", quotechar='"')
        csvarray = []

        for row in reader:
            csvarray.append(row)

        for row in csvarray:
            finding = Finding(test=test)
            findingdict = {}
            endpointdict = {}
            referencesarray = []

            for field, column_name in list(MAPPINGS.items()):
                if column_name == "IP":
                    urlfilter = Urlfilter()
                    urlfilter.eval_column(row[column_name])
                    endpointdict["host"] = urlfilter.host
                    endpointdict["path"] = urlfilter.path
                    endpointdict["query"] = urlfilter.query
                    endpointdict["fragment"] = urlfilter.fragment
                    findingdict["url"] = urlfilter.url
                elif column_name == "Severity":
                    severityfilter = Severityfilter()
                    severityfilter.eval_column(row[column_name])
                    findingdict["severity"] = severityfilter.severity
                elif column_name == "Port":
                    endpointdict[field] = row[column_name]
                elif column_name in ["Evidence", "CVE"]:
                    referencesarray.append(row[column_name])
                else:
                    if column_name in list(row.keys()):
                        findingdict[field] = row[column_name]

            try:
                dupe_endpoint = Endpoint.objects.get(
                    protocol=endpointdict["protocol"],
                    host=endpointdict["host"],
                    query=endpointdict["query"],
                    fragment=endpointdict["fragment"],
                    path=endpointdict["path"],
                    product=finding.test.engagement.product,
                )
            except:
                dupe_endpoint = None

            if not dupe_endpoint:
                endpoint = Endpoint(
                    protocol=endpointdict["protocol"],
                    host=endpointdict["host"],
                    query=endpointdict["query"],
                    fragment=endpointdict["fragment"],
                    path=endpointdict["path"],
                    product=finding.test.engagement.product,
                )
            else:
                endpoint = dupe_endpoint

            if not dupe_endpoint:
                endpoints = [endpoint]
            else:
                endpoints = [endpoint, dupe_endpoint]

            finding.unsaved_endpoints = endpoints
            finding.title = findingdict["title"]
            finding.description = findingdict["description"]
            finding.references = "\n".join(referencesarray)
            finding.mitigation = findingdict["mitigation"]
            finding.fqdn = findingdict["fqdn"]
            finding.severity = findingdict["severity"]
            finding.url = findingdict["url"]

            if finding is not None:
                if finding.url is None:
                    finding.url = ""
                if finding.title is None:
                    finding.title = ""
                if finding.description is None:
                    finding.description = ""

                key = hashlib.md5(
                    finding.url
                    + "|"
                    + finding.severity
                    + "|"
                    + finding.title
                    + "|"
                    + finding.description
                ).hexdigest()

                if key not in self.dupes:
                    self.dupes[key] = finding

        self.items = list(self.dupes.values())
