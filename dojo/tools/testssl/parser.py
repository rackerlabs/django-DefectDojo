import csv
import hashlib
import io
import re
from urllib.parse import urlparse

from dojo.models import Endpoint, Finding

__author__ = "dr3dd589"

SEV = ["INFO", "LOW", "HIGH", "WARN"]


class TestsslCSVParser(object):
    def get_findings(self, filename, test):
        content = filename.read()
        if type(content) is bytes:
            content = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter=",", quotechar='"')
        csvarray = []

        for row in reader:
            csvarray.append(row)
        dupes = dict()
        for row in csvarray:
            if row["severity"] in SEV:
                url = row["fqdn/ip"].split("/")[0]
                title = row["id"]
                severity = row["severity"].lower().capitalize()
                if severity == "Warn":
                    severity = "Info"
                cves = row["cve"].split(" ")
                description = "**Finding** : " + row["finding"] + "\n\n"
                if len(cves) > 1:
                    cve_desc = ""
                    cve = cves[0]
                    for cve_ in cves:
                        cve_desc += (
                            "[{0}](https://cve.mitre.org/cgi-bin/cvename.cgi?name={0})".format(
                                cve_
                            )
                            + ", "
                        )

                    description += "**Releted CVE's** : " + cve_desc[:-2]
                else:
                    try:
                        cve = cves[0]
                    except:
                        cve = None
                try:
                    cwe = re.findall(r"\d+", row["cwe"])[0]
                except:
                    cwe = None
                if title and description is not None:
                    dupe_key = hashlib.md5(
                        str(description + title).encode("utf-8")
                    ).hexdigest()
                    if dupe_key in dupes:
                        finding = dupes[dupe_key]
                        self.process_endpoints(finding, url)
                        dupes[dupe_key] = finding
                    else:
                        dupes[dupe_key] = True

                        finding = Finding(
                            title=title,
                            test=test,
                            active=False,
                            verified=False,
                            description=description,
                            severity=severity,
                            cve=cve,
                            cwe=cwe,
                            numerical_severity=Finding.get_numerical_severity(severity),
                        )
                        finding.unsaved_endpoints = list()
                        dupes[dupe_key] = finding
                        self.process_endpoints(finding, url)
        return dupes.values()

    def process_endpoints(self, finding, host):
        protocol = "http"
        query = ""
        fragment = ""
        path = ""
        url = urlparse(host)

        if url:
            path = url.path
            if path == host:
                path = ""

        rhost = re.search(
            r"(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
            host,
        )
        try:
            protocol = rhost.group(1)
            host = rhost.group(4)
        except:
            pass
        try:
            dupe_endpoint = Endpoint.objects.get(
                protocol=protocol, host=host, query=query, fragment=fragment, path=path
            )
        except Endpoint.DoesNotExist:
            dupe_endpoint = None

        if not dupe_endpoint:
            endpoint = Endpoint(
                protocol=protocol, host=host, query=query, fragment=fragment, path=path
            )
        else:
            endpoint = dupe_endpoint

        if not dupe_endpoint:
            endpoints = [endpoint]
        else:
            endpoints = [endpoint, dupe_endpoint]

        finding.unsaved_endpoints = finding.unsaved_endpoints + endpoints
