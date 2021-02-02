import csv
import hashlib
import io

from dojo.models import Finding

__author__ = "dr3dd589"


class CobaltCSVParser(object):
    def get_findings(self, filename, test):
        if filename is None:
            return list()

        content = filename.read()
        if type(content) is bytes:
            content = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter=",", quotechar='"')
        csvarray = []

        dupes = dict()

        # FIXME double loop, could lead to performance pb if the number of issues is big
        for row in reader:
            csvarray.append(row)

        for row in csvarray:
            finding = Finding(test=test)
            finding.title = row["Title"] if row["Title"][0] != "'" else row["Title"][1:]
            Type = row["Type"] if row["Type"][0] != "'" else row["Type"][1:]
            Description = (
                row["Description"]
                if row["Description"][0] != "'"
                else row["Description"][1:]
            )
            finding.description = (
                "**Type** : "
                + Type
                + "\n\n"
                + "**Description** : "
                + Description
                + "\n"
            )
            finding.mitigation = (
                row["SuggestedFix"]
                if row["SuggestedFix"][0] != "'"
                else row["SuggestedFix"][1:]
            )
            finding.references = (
                row["ResearcherUrl"]
                if row["ResearcherUrl"][0] != "'"
                else row["ResearcherUrl"][1:]
            )
            finding.steps_to_reproduce = (
                row["StepsToReproduce"]
                if row["StepsToReproduce"][0] != "'"
                else row["StepsToReproduce"][1:]
            )
            finding.severity_justification = (
                row["CriticalityJustification"]
                if row["CriticalityJustification"][0] != "'"
                else row["CriticalityJustification"][1:]
            )
            finding.severity = "Info"

            if finding is not None:
                if finding.title is None:
                    finding.title = ""
                if finding.description is None:
                    finding.description = ""

                key = hashlib.md5(
                    (finding.title + "|" + finding.description).encode("utf-8")
                ).hexdigest()

                if key not in dupes:
                    dupes[key] = finding

        return list(dupes.values())
