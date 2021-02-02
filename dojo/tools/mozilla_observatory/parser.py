import hashlib
import json
from urllib.parse import urlparse

from dojo.models import Endpoint, Finding

__author__ = "dr3dd589"


class MozillaObservatoryJSONParser(object):
    def get_findings(self, file, test):
        dupes = dict()
        data = file.read()
        try:
            tree = json.loads(str(data, "utf-8"))
        except:
            tree = json.loads(data)
        for content in tree:
            node = tree[content]
            if not node["pass"]:
                title = node["name"]
                description = (
                    "**Score Description** : "
                    + node["score_description"]
                    + "\n\n"
                    + "**Result** : "
                    + node["result"]
                    + "\n\n"
                    + "**expectation** : "
                    + node["expectation"]
                    + "\n"
                )
                severity = self.get_severity(int(node["score_modifier"]))
                mitigation = "N/A"
                impact = "N/A"
                references = "N/A"
                output = node["output"]
                try:
                    url = output["destination"]
                    parsedUrl = urlparse(url)
                    protocol = parsedUrl.scheme
                    query = parsedUrl.query
                    fragment = parsedUrl.fragment
                    path = parsedUrl.path
                    port = ""
                    try:
                        host, port = parsedUrl.netloc.split(":")
                    except:
                        host = parsedUrl.netloc
                except:
                    url = None

                dupe_key = hashlib.md5(
                    str(description + title).encode("utf-8")
                ).hexdigest()

                if dupe_key in dupes:
                    finding = dupes[dupe_key]
                    if finding.description:
                        finding.description = finding.description
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
                        impact=impact,
                        references=references,
                        dynamic_finding=True,
                    )
                    finding.unsaved_endpoints = list()
                    dupes[dupe_key] = finding

                    if url is not None:
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

    def get_severity(self, num_severity):
        if num_severity >= -10:
            return "Low"
        elif -11 >= num_severity > -26:
            return "Medium"
        elif num_severity <= -26:
            return "High"
        else:
            return "Info"
