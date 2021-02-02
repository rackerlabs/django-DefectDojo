from django.core.management.base import BaseCommand
from dojo.models import JIRA_Issue, JIRA_Instance
import dojo.jira_link.helper as jira_helper
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = (
        "Command to move data from some tables to other tables as part of https://github.com/DefectDojo/django-DefectDojo/pull/3200"
        + "Should normally be handled by the migration in that PR, but if that causes errors, this command can help to get the data migrated anyway."
    )

    def move_jira_creation_changed(self):
        logger.info(
            "migrating finding.jira_creation and jira_change fields to JIRA_Issue model"
        )
        for jira_issue in JIRA_Issue.objects.all().select_related("finding"):
            # try:
            if jira_issue.finding:
                logger.debug("populating jira_issue: %s", jira_issue.jira_key)
                jira_issue.jira_creation = jira_issue.finding.jira_creation
                jira_issue.jira_change = jira_issue.finding.jira_change
                jira_issue.save()
            else:
                logger.debug("no finding: skipping jira_issue: %s", jira_issue.jira_key)

    def populate_jira_project(self):
        logger.info(
            "populating jira_issue.jira_project to point to jira configuration of the product in defect dojo"
        )
        for jira_issue in (
            JIRA_Issue.objects.all()
            .select_related("jira_project")
            .prefetch_related("finding__test__engagement__product")
        ):
            # try:
            if not jira_issue.jira_project and jira_issue.finding:
                logger.info(
                    "populating jira_issue from finding: %s", jira_issue.jira_key
                )
                jira_project = jira_helper.get_jira_project(jira_issue.finding)
                # jira_project = jira_issue.finding.test.engagement.product.jira_project_set.all()[0]
                logger.debug("jira_project: %s", jira_project)
                jira_issue.jira_project = jira_project
                jira_issue.save()
            elif not jira_issue.jira_project and jira_issue.engagement:
                logger.debug(
                    "populating jira_issue from engagement: %s", jira_issue.jira_key
                )
                jira_project = jira_helper.get_jira_project(jira_issue.finding)
                # jira_project = jira_issue.engagement.product.jira_project_set.all()[0]
                logger.debug("jira_project: %s", jira_project)
                jira_issue.jira_project = jira_project
                jira_issue.save()
            elif not jira_issue.jira_project:
                logger.info(
                    "skipping %s as there is no finding or engagment",
                    jira_issue.jira_key,
                )

    def populate_jira_instance_name_if_empty(self):
        logger.info("populating JIRA_Instance.configuration_name with url if empty")
        for jira_instance in JIRA_Instance.objects.all():
            # try:
            if not jira_instance.configuration_name:
                jira_instance.configuration_name = jira_instance.url
                jira_instance.save()
            else:
                logger.debug(
                    "configuration_name already set for %i %s",
                    jira_instance.id,
                    jira_instance.url,
                )

    def handle(self, *args, **options):

        self.move_jira_creation_changed()
        self.populate_jira_project()
        self.populate_jira_instance_name_if_empty()

        logger.info(
            "now this script is completed, you can run the migration 0063_jira_refactor_populate as normal. it will skip over the data because it has already been populated"
        )
        logger.info(
            "if it still fails, comment out all the runpython parts, but leave the operations on the database fields in place"
        )
