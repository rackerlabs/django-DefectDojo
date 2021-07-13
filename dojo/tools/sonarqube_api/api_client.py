import requests

from dojo.models import Tool_Configuration, Tool_Type
from dojo.utils import prepare_for_view


class SonarQubeAPI:

    def __init__(self, tool_config=None):

        self.rules_cache = dict()

        tool_type, _ = Tool_Type.objects.get_or_create(name='SonarQube')

        if not tool_config:
            try:
                tool_config = Tool_Configuration.objects.get(tool_type=tool_type)
            except Tool_Configuration.DoesNotExist:
                raise Exception(
                    'No SonarQube tool is configured. \n'
                    'Create a new Tool at Settings -> Tool Configuration'
                )
            except Tool_Configuration.MultipleObjectsReturned:
                raise Exception(
                    'It has configured more than one SonarQube tool. \n'
                    'Please specify at Product configuration which one should be used.'
                )
        self.extras = tool_config.extras
        self.session = requests.Session()
        self.sonar_api_url = tool_config.url
        if tool_config.authentication_type == "Password":
            self.session.auth = (tool_config.username, prepare_for_view(tool_config.password))
        elif tool_config.authentication_type == "API":
            self.session.auth = (tool_config.api_key, '')
        else:
            raise Exception('SonarQube Authentication type {} not supported'.format(tool_config.authentication_type))

    def find_project(self, project_name):
        """
        Search for projects by name.
        :param project_name:
        :return:
        """
        response = self.session.get(
            url='{}/components/search'.format(self.sonar_api_url),
            params={
                'q': project_name,
                'qualifiers': 'TRK'
            },
            headers={
                'User-Agent': 'DefectDojo'
            },
        )

        if response.ok:
            for component in response.json().get('components', []):
                if component['name'] == project_name:
                    return component
            raise Exception(
                'Expected Project "{}", but it returned {}. \n'
                'Project Name is case sensitive and must match the DefectDojo Product Name. \n'
                'Alternatively it can also be specified the Project Key at Product configuration.'.format(
                    project_name,
                    [x.get('name') for x in response.json().get('components')]
                )
            )

        else:
            raise Exception("Unable to find the project {} due to {} - {}".format(
                project_name, response.status_code, response.content
            ))

    def get_project(self, project_key):
        """
        Returns a component (project).
        Requires the following permission: 'Browse' on the project of the specified component.
        :param project_key:
        :return:
        """
        response = self.session.get(
            url='{}/components/show'.format(self.sonar_api_url),
            params={
                'component': project_key,
            },
            headers={
                'User-Agent': 'DefectDojo'
            },
        )

        if response.ok:
            return response.json().get('component')
        else:
            raise Exception("Unable to find the project {} due to {} - {}".format(
                project_key, response.status_code, response.content
            ))

    def find_issues(self, component_key, types='VULNERABILITY'):
        """
        Search for issues.
        At most one of the following parameters can be provided at the same time:
            componentKeys, componentUuids, components, componentRootUuids, componentRoots.
        Requires the 'Browse' permission on the specified project(s).
        :param component_key: component key
        :param types: issue types (comma separated values). e.g. BUG,VULNERABILITY,CODE_SMELL
        :return:
        """

        if self.extras is not None:
            types = self.extras

        page = 1
        max_page = 100
        issues = list()

        while page <= max_page:
            request_filter = {
                'componentKeys': component_key,
                'types': types,
                'p': page
            }
            response = self.session.get(
                url='{}/issues/search'.format(self.sonar_api_url),
                params=request_filter,
                headers={
                    'User-Agent': 'DefectDojo'
                },
            )

            if response.ok:
                issues_page = response.json().get('issues')
                if not issues_page:
                    break
                issues.extend(issues_page)
                page += 1

            else:
                raise Exception(
                    "Unable to find the issues for component {} due to {} - {}".format(
                        component_key, response.status_code, response.content
                    )
                )

        return issues

    def find_hotspots(self, project_key):
        """
        Search for hotspots.
        :param project_key: project key
        :return:
        """
        page = 1
        max_page = 100
        hotspots = list()

        while page <= max_page:
            request_filter = {
                'projectKey': project_key,
                'p': page
            }
            response = self.session.get(
                url='{}/hotspots/search'.format(self.sonar_api_url),
                params=request_filter,
                headers={
                    'User-Agent': 'DefectDojo'
                },
            )

            if response.ok:
                hotspots_page = response.json().get('hotspots')
                if not hotspots_page:
                    break
                hotspots.extend(hotspots_page)
                page += 1

            else:
                raise Exception(
                    "Unable to find the hotspots for project {} due to {} - {}".format(
                        project_key, response.status_code, response.content
                    )
                )

        return hotspots

    def get_issue(self, issue_key):
        """
        Search for issues.
        At most one of the following parameters can be provided at the same time:
            componentKeys, componentUuids, components, componentRootUuids, componentRoots.
        Requires the 'Browse' permission on the specified project(s).
        :param issue_key:
        :return:
        """
        request_filter = {
            'issues': issue_key,
            'types': 'BUG,VULNERABILITY,CODE_SMELL'
        }
        response = self.session.get(
            url='{}/issues/search'.format(self.sonar_api_url),
            params=request_filter,
            headers={
                'User-Agent': 'DefectDojo'
            },
        )

        if response.ok:
            issues = response.json().get('issues', [])
            if issues:
                for issue in response.json().get('issues', []):
                    if issue['key'] == issue_key:
                        return issue
                raise Exception(
                    'Expected Issue "{}", but it returned {}.'.format(
                        issue_key,
                        [x.get('key') for x in response.json().get('issues')]
                    )
                )
        else:
            raise Exception(
                "Unable to get issue {} due to {} - {}".format(
                    issue_key, response.status_code, response.content
                )
            )

    def get_rule(self, rule_id):
        """
        Get detailed information about a rule
        :param rule_id:
        :return:
        """
        rule = self.rules_cache.get(rule_id)
        if not rule:
            response = self.session.get(
                url='{}/rules/show'.format(self.sonar_api_url),
                params={'key': rule_id},
                headers={
                    'User-Agent': 'DefectDojo'
                },
            )
            if response.ok:
                rule = response.json()['rule']
                self.rules_cache.update({rule_id: rule})
            else:
                raise Exception("Unable to get the rule {} due to {} - {}".format(
                    rule_id, response.status_code, response.content
                ))
        return rule

    def get_hotspot_rule(self, rule_id):
        """
        Get detailed information about a hotspot
        :param rule_id:
        :return:
        """
        rule = self.rules_cache.get(rule_id)
        if not rule:
            response = self.session.get(
                url='{}/hotspots/show'.format(self.sonar_api_url),
                params={'hotspot': rule_id},
                headers={
                    'User-Agent': 'DefectDojo'
                },
            )
            if response.ok:
                rule = response.json()['rule']
                self.rules_cache.update({rule_id: rule})
            else:
                raise Exception("Unable to get the hotspot rule {} due to {} - {}".format(
                    rule_id, response.status_code, response.content
                ))
        return rule

    def transition_issue(self, issue_key, transition):
        """
        Do workflow transition on an issue. Requires authentication and Browse permission on project.
        The transitions 'wontfix' and 'falsepositive' require the permission 'Administer Issues'.
        The transitions involving security hotspots (except 'requestreview') require
        the permission 'Administer Security Hotspot'.

        Possible transitions:
        - confirm
        - unconfirm
        - reopen
        - resolve
        - falsepositive
        - wontfix
        - close
        - detect
        - dismiss
        - reject
        - requestreview
        - accept
        - clear
        - reopenhotspot

        :param issue_key:
        :param transition:
        :return:
        """
        response = self.session.post(
            url='{}/issues/do_transition'.format(self.sonar_api_url),
            data={
                'issue': issue_key,
                'transition': transition
            },
            headers={
                'User-Agent': 'DefectDojo'
            },
        )
        if not response.ok:
            raise Exception(
                "Unable to transition {} the issue {} due to {} - {}".format(
                    transition, issue_key, response.status_code, response.content
                )
            )

    def add_comment(self, issue_key, text):
        """
        Add a comment.
        Requires authentication and the following permission: 'Browse' on the project of the specified issue.
        :param issue_key:
        :param text:
        :return:
        """
        response = self.session.post(
            url='{}/issues/add_comment'.format(self.sonar_api_url),
            data={
                'issue': issue_key,
                'text': text
            },
            headers={
                'User-Agent': 'DefectDojo'
            },
        )
        if not response.ok:
            raise Exception(
                "Unable to add a comment into issue {} due to {} - {}".format(
                    issue_key, response.status_code, response.content
                )
            )
