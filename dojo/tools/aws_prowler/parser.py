
import re
from datetime import datetime
import sys
import io
import csv
from django.utils.text import Truncator

from dojo.models import Finding


class AWSProwlerParser(object):

    def get_scan_types(self):
        return ["AWS Prowler Scan"]

    def get_label_for_scan_types(self, scan_type):
        return "AWS Prowler Scan"

    def get_description_for_scan_types(self, scan_type):
        return "AWS Security Hub exports in JSON format."

    def get_findings(self, filename, test):
        content = filename.read()
        if type(content) is bytes:
            content = content.decode('utf-8')
        csv.field_size_limit(int(sys.maxsize / 10))  # the request/resp are big
        reader = csv.DictReader(io.StringIO(content))
        dupes = dict()

        find_date = datetime.now()
        account = None

        for row in reader:
            profile = str(row.get('PROFILE'))
            account = str(row.get('ACCOUNT_NUM'))
            region = str(row.get('REGION'))
            title_id = str(row.get('TITLE_ID'))
            result = str(row.get('RESULT'))
            scored = str(row.get('SCORED'))
            level = str(row.get('LEVEL'))
            severity = str(row.get('SEVERITY'))
            title_text = str(row.get('TITLE_TEXT'))
            title_text = str(re.sub(r'\[.*\]\s', '', title_text))
            title_text_trunc = Truncator(title_text).words(8)
            notes = str(row.get('NOTES'))

            sev = self.getCriticalityRating(result, level, severity)
            description = "**Region:** " + region + "\n\n" + notes + "\n"
            dupe_key = sev + title_text
            if dupe_key in dupes:
                find = dupes[dupe_key]
                if description is not None:
                    find.description += description + "\n\n"
            else:
                find = Finding(title=title_text_trunc,
                               cwe=1032,  # Security Configuration Weaknesses, would like to fine tune
                               test=test,
                               active=False,
                               verified=False,
                               description="**AWS Account:** " + str(account) + "\n**Control:** " + title_text + "\n**CIS Control:** " + str(title_id) + ", " + level + "\n\n" + description,
                               severity=sev,
                               numerical_severity=Finding.get_numerical_severity(sev),
                               references=None,
                               date=find_date,
                               dynamic_finding=True)
                dupes[dupe_key] = find

        if account:
            test_description = ""
            test_description = "%s\n* **AWS Account:** %s\n" % (test_description, str(account))
            test.description = test_description
            test.save()
        return list(dupes.values())

    def formatview(self, depth):
        if depth > 1:
            return "* "
        else:
            return ""

    # Criticality rating
    def getCriticalityRating(self, result, level, severity):
        criticality = "Info"
        if result == "INFO" or result == "PASS":
            criticality = "Info"
        elif result == "FAIL":
            if severity:
                return severity
            else:
                if level == "Level 1":
                    criticality = "Critical"
                else:
                    criticality = "High"

        return criticality
