import logging

from django.utils import timezone

from dojo.models import Finding, Risk_Acceptance
from dojo.tools.sonarqube_api.api_client import SonarQubeAPI

logger = logging.getLogger(__name__)


class SonarQubeApiUpdaterFromSource(object):
    """
    The responsibility of this class is to update the Finding status if current SonarQube issue status doesn't match.

    This way, findings will be updated based on SonarQube information when SonarQube is updated manually and
    already imported in DefectDojo.
    """

    @staticmethod
    def get_findings_to_update():
        return Finding.objects.filter(
            sonarqube_issue__isnull=False,
            active=True,
        ).select_related("sonarqube_issue")

    def update(self, finding):
        sonarqube_issue = finding.sonarqube_issue
        if not sonarqube_issue:
            return

        product = finding.test.engagement.product
        config = product.sonarqube_product_set.all().first()

        client = SonarQubeAPI(
            tool_config=config.sonarqube_tool_config if config else None
        )
        issue = client.get_issue(sonarqube_issue.key)
        if (
            issue
        ):  # Issue could have disappeared in SQ because a previous scan has resolved the issue as fixed
            current_status = issue.get("resolution") or issue.get("status")
            current_finding_status = self.get_sonarqube_status_for(finding)
            logger.debug(
                "--> SQ Current status: {}. Finding status: {}".format(
                    current_status, current_finding_status
                )
            )

            if current_status != "OPEN" and current_finding_status != current_status:
                logger.info(
                    "Original SonarQube issue '{}' has changed. Updating DefectDojo finding '{}'...".format(
                        sonarqube_issue, finding
                    )
                )
                self.update_finding_status(finding, current_status)

    @staticmethod
    def get_sonarqube_status_for(finding):
        target_status = None
        if finding.false_p:
            target_status = "FALSE-POSITIVE"
        elif finding.mitigated or finding.is_Mitigated:
            target_status = "FIXED"
        elif finding.risk_accepted:
            target_status = "WONTFIX"
        elif finding.active:
            if finding.verified:
                target_status = "CONFIRMED"
            else:
                target_status = "REOPENED"
        return target_status

    @staticmethod
    def update_finding_status(finding, sonarqube_status):
        if sonarqube_status in ["OPEN", "REOPENED"]:
            finding.active = True
            finding.verified = False
            finding.false_p = False
            finding.mitigated = None
            finding.is_Mitigated = False
            ra_helper.remove_finding.from_any_risk_acceptance(finding)

        elif sonarqube_status == "CONFIRMED":
            finding.active = True
            finding.verified = True
            finding.false_p = False
            finding.mitigated = None
            finding.is_Mitigated = False
            ra_helper.remove_finding.from_any_risk_acceptance(finding)

        elif sonarqube_status == "FIXED":
            finding.active = False
            finding.verified = True
            finding.false_p = False
            finding.mitigated = timezone.now()
            finding.is_Mitigated = True
            ra_helper.remove_finding.from_any_risk_acceptance(finding)

        elif sonarqube_status == "WONTFIX":
            finding.active = False
            finding.verified = True
            finding.false_p = False
            finding.mitigated = None
            finding.is_Mitigated = False
            Risk_Acceptance.objects.create(
                owner=finding.reporter,
            ).accepted_findings.set([finding])

        elif sonarqube_status == "FALSE-POSITIVE":
            finding.active = False
            finding.verified = False
            finding.false_p = True
            finding.mitigated = None
            finding.is_Mitigated = False
            ra_helper.remove_finding.from_any_risk_acceptance(finding)

        finding.save(issue_updater_option=False, dedupe_option=False)
