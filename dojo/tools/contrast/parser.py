import csv
import hashlib
import io
import sys

from dojo.models import Endpoint, Finding


class ContrastCSVParser(object):
    """Contrast Scanner CSV Report"""

    def get_findings(self, filename, test):
        content = filename.read()
        if type(content) is bytes:
            content = content.decode("utf-8")
        csv.field_size_limit(int(sys.maxsize / 10))  # the request/resp are big
        reader = csv.DictReader(io.StringIO(content))
        dupes = dict()

        for row in reader:
            # Vulnerability Name,Vulnerability ID,Category,Rule Name,Severity,Status,Number of Events,First Seen,Last Seen,Application Name,Application ID,Application Code,CWE ID,Request Method,Request Port,Request Protocol,Request Version,Request URI,Request Qs,Request Body
            cwe = self.format_cwe(row.get("CWE ID"))
            title = row.get("Vulnerability Name")
            category = row.get("Category")
            description = self.format_description(row)
            severity = row.get("Severity")
            if severity == "Note":
                severity = "Info"
            mitigation = "N/A"
            impact = "N/A"
            references = "N/A"

            dupe_key = hashlib.md5(
                category.encode("utf-8")
                + str(cwe).encode("utf-8")
                + title.encode("utf-8")
            ).hexdigest()

            if dupe_key in dupes:
                finding = dupes[dupe_key]
                if finding.description:
                    finding.description = (
                        finding.description
                        + "\nVulnerability ID: "
                        + row.get("Vulnerability ID")
                        + "\n"
                        + row.get("Vulnerability Name")
                        + "\n"
                    )
                self.process_endpoints(finding, df, i)
                dupes[dupe_key] = finding
            else:
                dupes[dupe_key] = True

                finding = Finding(
                    title=title,
                    cwe=cwe,
                    test=test,
                    active=False,
                    verified=False,
                    description=description,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation=mitigation,
                    impact=impact,
                    references=references,
                    vuln_id_from_tool=row.get("Vulnerability ID"),
                    dynamic_finding=True,
                )

                dupes[dupe_key] = finding
                self.process_endpoints(finding, row)

        return list(dupes.values())

    def format_description(self, row):
        description = "**Request URI**: " + str(row.get("Request URI")) + "\n"
        description = description + "**Rule Name:** " + row.get("Rule Name") + "\n"
        description = (
            description + "**Vulnerability ID:** " + row.get("Vulnerability ID") + "\n"
        )
        description = (
            description
            + "**Vulnerability Name:** "
            + row.get("Vulnerability Name")
            + "\n"
        )
        description = description + "**Status:** " + row.get("Status") + "\n"
        return description

    def format_cwe(self, url):
        # Get the last path
        filename = url.rsplit("/", 1)[1]

        # Split out the . to get the CWE id
        filename = filename.split(".")[0]

        return int(filename)

    def process_endpoints(self, finding, row):
        protocol = "http"
        host = "0.0.0.0"
        query = ""
        fragment = ""
        path = row.get("Request URI")

        if path:
            try:
                dupe_endpoint = Endpoint.objects.get(
                    protocol="protocol",
                    host=host,
                    query=query,
                    fragment=fragment,
                    path=path,
                    product=finding.test.engagement.product,
                )
            except Endpoint.DoesNotExist:
                dupe_endpoint = None

            if not dupe_endpoint:
                endpoint = Endpoint(
                    protocol=protocol,
                    host=host,
                    query=query,
                    fragment=fragment,
                    path=path,
                    product=finding.test.engagement.product,
                )
            else:
                endpoint = dupe_endpoint

            if not dupe_endpoint:
                endpoints = [endpoint]
            else:
                endpoints = [endpoint, dupe_endpoint]

            finding.unsaved_endpoints = finding.unsaved_endpoints + endpoints

        if row.get("Request Qs", "") != "" and row.get("Request Body", "") != "":
            finding.unsaved_req_resp = []
            finding.unsaved_req_resp.append(
                {
                    "req": row.get("Request Qs") + "\n" + row.get("Request Body"),
                    "resp": "",
                }
            )
