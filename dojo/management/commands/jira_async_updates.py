from django.core.management.base import BaseCommand
from django.utils import timezone
from jira.exceptions import JIRAError

from dojo.models import Finding, Notes, User, Dojo_User

"""
Author: Aaron Weaver
This script will locate open, active findings and update them in JIRA.
Useful if you need to make bulk changes with JIRA:
"""


class Command(BaseCommand):
    help = "No input commands for JIRA bulk update."

    def handle(self, *args, **options):

        findings = Finding.objects.exclude(jira_issue__isnull=True)
        findings = findings.filter(verified=True, active=True)
        findings = findings.prefetch_related("jira_issue")
        # finding = Finding.objects.get(id=1)
        for finding in findings:
            #    try:
            JIRAError.log_to_tempfile = False
            jira = jira_helper.get_jira_connection(finding)
            j_issue = finding.jira_issue
            issue = jira.issue(j_issue.jira_id)

            # Issue Cloned
            print(issue.fields.issuelinks[0])

            print("Jira Issue: " + str(issue))
            print("Resolution: " + str(issue.fields.resolution))

            if issue.fields.resolution is not None and not finding.under_defect_review:
                # print issue.fields.__dict__
                print("Jira Issue: " + str(issue) + " changed status")

                # Create Jira Note
                now = timezone.now()
                new_note = Notes()
                new_note.entry = (
                    "Please Review Jira Request: "
                    + str(issue)
                    + ". Review status has changed to "
                    + str(issue.fields.resolution)
                    + "."
                )
                new_note.author = User.objects.get(username="JIRA")
                new_note.date = now
                new_note.save()
                finding.notes.add(new_note)
                finding.under_defect_review = True
                dojo_user = Dojo_User.objects.get(username="JIRA")
                finding.defect_review_requested_by = dojo_user

                # Create alert to notify user
                jira_helper.log_jira_message(
                    "Jira issue status change, please review.", finding
                )
                finding.save()
            else:
                print("No update necessary")
