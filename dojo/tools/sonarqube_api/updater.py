import logging
from collections import deque

from dojo.models import Sonarqube_Issue_Transition
from dojo.tools.sonarqube_api.importer import SonarQubeApiImporter

logger = logging.getLogger(__name__)


class SonarQubeApiUpdater(object):
    """
    This class updates in SonarQube, a SonarQube issue previously imported as a DefectDojo Findings.
     This class maps the finding status to a SQ issue status and later on it transitions the issue
     properly to a consistent status.
     This way, findings marked as resolved, false positive or accepted in DefectDojo won't reappear
     in future imports of SonarQube Scanner.
    """

    MAPPING_SONARQUBE_STATUS_TRANSITION = [
        {
            'from': ['OPEN', 'REOPENED'],
            'to': 'REOPENED',
            'transition': None
        },
        {
            'from': ['OPEN', 'REOPENED'],
            'to': 'CONFIRMED',
            'transition': 'confirm'
        }, {
            'from': ['CONFIRMED'],
            'to': 'REOPENED',
            'transition': 'unconfirm'
        }, {
            'from': ['OPEN', 'REOPENED', 'CONFIRMED'],
            'to': 'RESOLVED / FIXED',
            'transition': 'resolve'
        }, {
            'from': ['OPEN', 'REOPENED', 'CONFIRMED'],
            'to': 'RESOLVED / WONTFIX',
            'transition': 'wontfix'
        }, {
            'from': ['OPEN', 'REOPENED', 'CONFIRMED'],
            'to': 'RESOLVED / FALSE-POSITIVE',
            'transition': 'falsepositive'
        }, {
            'from': ['RESOLVED / FIXED', 'RESOLVED / WONTFIX', 'RESOLVED / FALSE-POSITIVE'],
            'to': 'REOPENED',
            'transition': 'reopen'
        },
    ]

    @staticmethod
    def get_sonarqube_status_for(finding):
        target_status = None
        if finding.false_p:
            target_status = 'RESOLVED / FALSE-POSITIVE'
        elif finding.mitigated or finding.is_mitigated:
            target_status = 'RESOLVED / FIXED'
        elif finding.risk_accepted:
            target_status = 'RESOLVED / WONTFIX'
        elif finding.active:
            if finding.verified:
                target_status = 'CONFIRMED'
            else:
                target_status = 'REOPENED'
        return target_status

    def get_sonarqube_required_transitions_for(self, current_status, target_status):

        # If current and target is the same... do nothing
        if current_status == target_status:
            return

        # Check if there is at least one transition from current_status...
        if not [x for x in self.MAPPING_SONARQUBE_STATUS_TRANSITION if current_status in x.get('from')]:
            return

        # Starting from target_status... find out possible origin statuses that can transition to target_status
        transitions = [x for x in self.MAPPING_SONARQUBE_STATUS_TRANSITION if target_status == x.get('to')]
        if transitions:
            for transition in transitions:
                # There is a direct transition from current status...
                if current_status in transition.get('from'):
                    t = transition.get('transition')
                    return [t] if t else None

            # We have the last transition to get to our target status but there is no direct transition
            transitions_result = deque()
            transitions_result.appendleft(transitions[0].get('transition'))

            # Find out previous transitions that would finish in any FROM of a previous to use as target
            for transition in transitions:
                for t_from in transition.get('from'):
                    possible_transition = self.get_sonarqube_required_transitions_for(current_status, t_from)
                    if possible_transition:
                        transitions_result.extendleft(possible_transition)
                        return list(transitions_result)

    def update_sonarqube_finding(self, finding):

        sonarqube_issue = finding.sonarqube_issue
        if not sonarqube_issue:
            return

        logger.debug("Checking if finding '{}' needs to be updated in SonarQube".format(finding))

        client, _ = SonarQubeApiImporter.prepare_client(finding.test)
        # we don't care about config, each finding knows which config was used during import

        target_status = self.get_sonarqube_status_for(finding)

        issue = client.get_issue(sonarqube_issue.key)
        if issue.get('resolution'):
            current_status = '{} / {}'.format(issue.get('status'), issue.get('resolution'))
        else:
            current_status = issue.get('status')

        logger.debug("--> SQ Current status: {}. Current target status: {}".format(current_status, target_status))

        transitions = self.get_sonarqube_required_transitions_for(current_status, target_status)
        if transitions:
            logger.info("Updating finding '{}' in SonarQube".format(finding))

            for transition in transitions:
                client.transition_issue(sonarqube_issue.key, transition)

            # Track Defect Dojo has updated the SonarQube issue
            Sonarqube_Issue_Transition.objects.create(
                sonarqube_issue=finding.sonarqube_issue,
                # not sure if this is needed, but looks like the original author decided to send display status to sonarcube
                # we changed Accepted into Risk Accepted, but we change it back to be sure we don't break the integration
                finding_status=finding.status().replace('Risk Accepted', 'Accepted') if finding.status() else finding.status(),
                sonarqube_status=current_status,
                transitions=','.join(transitions),
            )
