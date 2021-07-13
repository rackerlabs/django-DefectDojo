import logging
import re

import html2text
from lxml import etree

from dojo.models import Finding, Sonarqube_Issue
from dojo.notifications.helper import create_notification
from dojo.tools.sonarqube_api.api_client import SonarQubeAPI

logger = logging.getLogger(__name__)


class SonarQubeApiImporter(object):
    """
    This class imports from SonarQube (SQ) all open/confirmed SQ issues related to the project related to the test as
     findings.
    """

    def get_findings(self, filename, test):
        items = self.import_issues(test)
        items.extend(self.import_hotspots(test))
        return items

    @staticmethod
    def is_confirmed(state):
        return state.lower() in [
            'confirmed',
            'accepted',
            'detected',
        ]

    @staticmethod
    def is_closed(state):
        return state.lower() in [
            'resolved',
            'falsepositive',
            'wontfix',
            'closed',
            'dismissed',
            'rejected'
        ]

    @staticmethod
    def is_reviewed(state):
        return state.lower() in [
            'reviewed'
        ]

    def import_issues(self, test):

        items = list()

        try:
            product = test.engagement.product
            config = product.sonarqube_product_set.all().first()

            client = SonarQubeAPI(
                tool_config=config.sonarqube_tool_config if config else None
            )

            if config and config.sonarqube_project_key:
                component = client.get_project(config.sonarqube_project_key)
            else:
                component = client.find_project(product.name)

            issues = client.find_issues(component['key'])
            logging.info('Found {} issues for component {}'.format(len(issues), component["key"]))

            for issue in issues:
                status = issue['status']
                from_hotspot = issue.get('fromHotspot', False)

                if self.is_closed(status) or from_hotspot:
                    continue

                type = issue['type']
                if len(issue['message']) > 511:
                    title = issue['message'][0:507] + "..."
                else:
                    title = issue['message']
                component_key = issue['component']
                line = issue.get('line')
                rule_id = issue['rule']
                rule = client.get_rule(rule_id)
                severity = self.convert_sonar_severity(rule['severity'])
                description = self.clean_rule_description_html(rule['htmlDesc'])
                cwe = self.clean_cwe(rule['htmlDesc'])
                references = self.get_references(rule['htmlDesc'])

                sonarqube_issue, _ = Sonarqube_Issue.objects.update_or_create(
                    key=issue['key'],
                    defaults={
                        'status': status,
                        'type': type,
                    }
                )

                # Only assign the SonarQube_issue to the first finding related to the issue
                if Finding.objects.filter(sonarqube_issue=sonarqube_issue).exists():
                    sonarqube_issue = None

                find = Finding(
                    title=title,
                    cwe=cwe,
                    description=description,
                    test=test,
                    severity=severity,
                    references=references,
                    file_path=component_key,
                    line=line,
                    verified=self.is_confirmed(status),
                    false_p=False,
                    duplicate=False,
                    out_of_scope=False,
                    mitigated=None,
                    mitigation='No mitigation provided',
                    impact="No impact provided",
                    static_finding=True,
                    sonarqube_issue=sonarqube_issue,
                )
                items.append(find)

        except Exception as e:
            logger.exception(e)
            create_notification(
                event='other',
                title='SonarQube API import issue',
                description=e,
                icon='exclamation-triangle',
                source='SonarQube API'
            )

        return items

    def import_hotspots(self, test):

        items = list()

        try:
            product = test.engagement.product
            config = product.sonarqube_product_set.all().first()

            client = SonarQubeAPI(
                tool_config=config.sonarqube_tool_config if config else None
            )

            if config and config.sonarqube_project_key:
                project = client.get_project(config.sonarqube_project_key)
            else:
                project = client.find_project(product.name)

            hotspots = client.find_hotspots(project['key'])
            logging.info('Found {} hotspots for project {}'.format(len(hotspots), project["key"]))

            for hotspot in hotspots:
                status = hotspot['status']

                if self.is_reviewed(status):
                    continue

                type = 'SECURITY_HOTSPOT'
                if len(hotspot['message']) > 511:
                    title = hotspot['message'][0:507] + "..."
                else:
                    title = hotspot['message']
                component_key = hotspot['component']
                line = hotspot.get('line')
                rule_id = hotspot['key']
                rule = client.get_hotspot_rule(rule_id)
                severity = self.convert_sonar_review_priority(rule['vulnerabilityProbability'])
                description = self.clean_rule_description_html(rule['vulnerabilityDescription'])
                cwe = self.clean_cwe(rule['riskDescription'])
                references = self.get_references(rule['riskDescription'])

                sonarqube_issue, _ = Sonarqube_Issue.objects.update_or_create(
                    key=hotspot['key'],
                    defaults={
                        'status': status,
                        'type': type
                    }
                )

                # Only assign the SonarQube_issue to the first finding related to the issue
                if Finding.objects.filter(sonarqube_issue=sonarqube_issue).exists():
                    sonarqube_issue = None

                find = Finding(
                    title=title,
                    cwe=cwe,
                    description=description,
                    test=test,
                    severity=severity,
                    references=references,
                    file_path=component_key,
                    line=line,
                    active=True,
                    verified=self.is_confirmed(status),
                    false_p=False,
                    duplicate=False,
                    out_of_scope=False,
                    static_finding=True,
                    sonarqube_issue=sonarqube_issue,
                )
                items.append(find)

        except Exception as e:
            logger.exception(e)
            create_notification(
                event='other',
                title='SonarQube API hotspot import issue',
                description=e,
                icon='exclamation-triangle',
                source='SonarQube API'
            )

        return items

    @staticmethod
    def clean_rule_description_html(raw_html):
        search = re.search(r"^(.*?)(?:(<h2>See</h2>)|(<b>References</b>))", raw_html, re.DOTALL)
        if search:
            raw_html = search.group(1)
        h = html2text.HTML2Text()
        raw_html = raw_html.replace('<h2>', '<b>').replace('</h2>', '</b>')
        return h.handle(raw_html)

    @staticmethod
    def clean_cwe(raw_html):
        search = re.search(r'CWE-(\d+)', raw_html)
        if search:
            return int(search.group(1))

    @staticmethod
    def convert_sonar_severity(sonar_severity):
        sev = sonar_severity.lower()
        if sev == "blocker":
            return "Critical"
        elif sev == "critical":
            return "High"
        elif sev == "major":
            return "Medium"
        elif sev == "minor":
            return "Low"
        else:
            return "Info"

    @staticmethod
    def convert_sonar_review_priority(sonar_review_priority):
        sev = sonar_review_priority.lower()
        if sev == "high":
            return "High"
        elif sev == "medium":
            return "Medium"
        elif sev == "low":
            return "Low"
        else:
            return "Info"

    @staticmethod
    def get_references(vuln_details):
        parser = etree.HTMLParser()
        details = etree.fromstring(vuln_details, parser)
        rule_references = ""
        for a in details.iter("a"):
            rule_references += "[{}]({})\n".format(a.text, a.get('href'))
        return rule_references
