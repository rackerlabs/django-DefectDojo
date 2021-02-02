import logging
import hashlib
import json
from urllib.parse import urlparse

from dojo.models import Endpoint, Finding

__author__ = "dr3dd589"


class WpscanJSONParser(object):
    """WPScan – WordPress Security Scanner"""

    def get_findings(self, file, test):
        if file is None:
            return list()
        data = file.read()
        try:
            tree = json.loads(str(data, "utf-8"))
        except:
            tree = json.loads(data)

        logging.debug("Parse Wpscan file")
        dupes = dict()
        for content in tree:
            node = tree[content]
            vuln_arr = []
            try:
                vuln_arr = node["vulnerabilities"]
            except:
                pass
            if "plugins" in content:
                for plugin_content in node:
                    vuln_arr = node[plugin_content]["vulnerabilities"]
            target_url = tree["target_url"]
            parsedUrl = urlparse(target_url)
            protocol = parsedUrl.scheme
            query = parsedUrl.query
            fragment = parsedUrl.fragment
            path = parsedUrl.path
            port = ""
            try:
                (host, port) = parsedUrl.netloc.split(":")
            except:
                host = parsedUrl.netloc

            for vul in vuln_arr:
                title = vul["title"]
                references = (
                    "\n".join(vul["references"]["url"])
                    + "\n"
                    + "**wpvulndb : **"
                    + str(vul["references"]["wpvulndb"])
                )
                try:
                    mitigation = "fixed in : " + vul["fixed_in"]
                except:
                    mitigation = "N/A"
                severity = "Info"
                description = "**Title : **" + title
                dupe_key = hashlib.md5(
                    str(references + title).encode("utf-8")
                ).hexdigest()
                if dupe_key in dupes:
                    finding = dupes[dupe_key]
                    if finding.references:
                        finding.references = finding.references
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
                        numerical_severity=Finding.get_numerical_severity(severity),
                        mitigation=mitigation,
                        references=references,
                        dynamic_finding=True,
                    )
                    finding.unsaved_endpoints = list()
                    dupes[dupe_key] = finding

                    if target_url is not None:
                        finding.unsaved_endpoints.append(
                            Endpoint(
                                host=host,
                                port=port,
                                path=path,
                                protocol=protocol,
                                query=query,
                                fragment=fragment,
                            )
                        )
        return dupes.values()
