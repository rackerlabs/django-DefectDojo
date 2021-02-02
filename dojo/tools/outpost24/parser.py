import logging

from defusedxml import ElementTree

from dojo.models import Endpoint, Finding

logger = logging.getLogger(__name__)


class Outpost24Parser:
    def get_findings(self, file, test):
        tree = ElementTree.parse(file)
        items = list()
        for detail in tree.iterfind("//detaillist/detail"):
            # finding details
            title = detail.findtext("name")
            # date = detail.findtext('date') # can be used for Finding.date?
            cve = detail.findtext("./cve/id")
            url = detail.findtext("./referencelist/reference/[type='solution']/../url")
            description = detail.findtext("description")
            mitigation = detail.findtext("solution")
            impact = detail.findtext("information")
            cvss_score = detail.findtext("cvss_v3_score") or detail.findtext(
                "cvss_score"
            )
            if not cvss_score:
                cvss_score = 0
            if cvss_score:
                score = float(cvss_score)
                if score < 4:
                    severity = "Low"
                elif score < 7:
                    severity = "Medium"
                elif score < 9:
                    severity = "High"
                else:
                    severity = "Critical"
            else:
                risk = int(detail.findtext("risk"))
                if risk == 0:
                    severity = "Low"
                elif risk == 1:
                    severity = "Medium"
                elif risk == 2:
                    severity = "High"
                else:
                    severity = "Critical"
            cvss_description = detail.findtext("cvss_vector_description")
            cvss_vector = detail.findtext("cvss_v3_vector") or detail.findtext(
                "cvss_vector"
            )
            severity_justification = "{}\n{}".format(cvss_score, cvss_description)
            finding = Finding(
                title=title,
                test=test,
                cve=cve,
                url=url,
                description=description,
                mitigation=mitigation,
                impact=impact,
                severity=severity,
                numerical_severity=cvss_score,
                severity_justification=severity_justification,
            )
            # endpoint details
            host = detail.findtext("ip")
            if host:
                protocol = detail.findtext("./portinfo/service")
                try:
                    port = int(detail.findtext("./portinfo/portnumber"))
                except ValueError as ve:
                    logger.debug("General port given. Assigning 0 as default.")
                    port = 0
                finding.unsaved_endpoints.append(
                    Endpoint(protocol=protocol, host=host, port=port)
                )
            items.append(finding)
        return items
