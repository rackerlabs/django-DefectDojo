from django.core.management.base import BaseCommand

from pytz import timezone
from dojo.models import Finding, Finding_Template
from dojo.utils import get_system_setting

locale = timezone(get_system_setting("time_zone"))

"""
Authors: Jay Paz
Finding Templates have been revamped and have their own model.  The is_template field on Findings will no longer be used
for this purpose.  This script will migrate all Findings wiht the is_template field set to True into the new model
Finding_Template.
"""


class Command(BaseCommand):
    help = (
        "Finding Templates have been revamped and have their own model.  The is_template field on Findings will "
        "no longer be used for this purpose.  This script will migrate all Findings wiht the is_template field "
        "set to True into the new model Finding_Template."
    )

    def handle(self, *args, **options):
        findings = Finding.objects.filter(is_template=True)
        count = 0
        for finding in findings:
            template = Finding_Template(
                title=finding.title,
                cwe=finding.cwe,
                severity=finding.severity,
                description=finding.description,
                mitigation=finding.mitigation,
                impact=finding.impact,
                references=finding.references,
                numerical_severity=finding.numerical_severity,
            )
            template.save()
            finding.is_template = False
            finding.save()
            count += 1

        print("A total of %d findings have been turned into templates." % count)
