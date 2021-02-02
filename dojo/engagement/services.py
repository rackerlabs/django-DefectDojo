# #  engagements
import logging

from django.utils import timezone
import dojo.jira_link.helper as jira_helper

logger = logging.getLogger(__name__)


def close_engagement(eng):
    eng.active = False
    eng.status = "Completed"
    eng.updated = timezone.now()
    eng.save()

    if jira_helper.get_jira_project(eng):
        jira_helper.close_epic(eng, True)


def reopen_engagement(eng):
    eng.active = True
    eng.status = "In Progress"
    eng.save()
