import hashlib
import json
from datetime import datetime

from dojo.models import Finding

__author__ = "Kirill Gotsman"


class HackerOneJSONParser(object):
    """
    A class that can be used to parse the Get All Reports JSON export from HackerOne API.
    """

    def get_findings(self, file, test):
        """
        Converts a HackerOne reports to a DefectDojo finding
        """

        # Load the contents of the JSON file into a dictionary
        data = file.read()
        try:
            tree = json.loads(str(data, "utf-8"))
        except:
            tree = json.loads(data)
        # Convert JSON  report to DefectDojo format
        dupes = dict()
        for content in tree["data"]:
            # Get all relevant data
            date = content["attributes"]["created_at"]
            date = datetime.strftime(
                datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ"), "%Y-%m-%d"
            )
            # Build the title of the Dojo finding
            title = "#" + content["id"] + " " + content["attributes"]["title"]

            description = self.build_description(content)

            # References
            try:
                issue_tracker_id = content["attributes"]["issue_tracker_reference_id"]
                issue_tracker_url = content["attributes"]["issue_tracker_reference_url"]
                references = "[{}]({})\n".format(issue_tracker_id, issue_tracker_url)
            except:
                references = ""

            # Build the severity of the Dojo finding
            try:
                severity = content["relationships"]["severity"]["data"]["attributes"][
                    "rating"
                ].capitalize()
                if severity not in ["Low", "Medium", "High", "Critical"]:
                    severity = "Info"
            except:
                severity = "Info"
            # Build the references of the Dojo finding
            ref_link = "https://hackerone.com/reports/{}".format(content.get("id"))
            references += "[{}]({})".format(ref_link, ref_link)

            # Set active state of the Dojo finding
            if content["attributes"]["state"] in ["triaged", "new"]:
                active = True
            else:
                active = False

            # Set CWE of the Dojo finding
            try:
                cwe = int(
                    content["relationships"]["weakness"]["data"]["attributes"][
                        "external_id"
                    ][4:]
                )
            except:
                cwe = 0

            dupe_key = hashlib.md5(str(references + title).encode("utf-8")).hexdigest()
            if dupe_key in dupes:
                finding = dupes[dupe_key]
                if finding.references:
                    finding.references = finding.references
                dupes[dupe_key] = finding
            else:
                dupes[dupe_key] = True

                # Build and return Finding model
                finding = Finding(
                    title=title,
                    unique_id_from_tool=dupe_key,
                    date=date,
                    test=test,
                    active=active,
                    description=description,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation="See description",
                    impact="No impact provided",
                    references=references,
                    cwe=cwe,
                    dynamic_finding=False,
                )
                finding.unsaved_endpoints = list()
                dupes[dupe_key] = finding
        return dupes.values()

    def build_description(self, content):
        date = content["attributes"]["created_at"]
        date = datetime.strftime(
            datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ"), "%Y-%m-%d"
        )
        reporter = content["relationships"]["reporter"]["data"]["attributes"][
            "username"
        ]
        triaged_date = content["attributes"]["triaged_at"]

        # Build the description of the Dojo finding
        description = "#" + content["attributes"]["title"]
        description += "\nSubmitted: {}\nBy: {}\n".format(date, reporter)

        # Add triaged date
        if triaged_date is not None:
            triaged_date = datetime.strftime(
                datetime.strptime(triaged_date, "%Y-%m-%dT%H:%M:%S.%fZ"), "%Y-%m-%d"
            )
            description += "Triaged: {}\n".format(triaged_date)

        # Try to grab CVSS
        try:
            cvss = content["relationships"]["severity"]["data"]["attributes"]["score"]
            description += "CVSS: {}\n".format(cvss)
        except:
            pass

        # Build rest of description meat
        description += "##Report: \n{}\n".format(
            content["attributes"]["vulnerability_information"]
        )

        # Try to grab weakness if it's there
        try:
            weakness_title = content["relationships"]["weakness"]["data"]["attributes"][
                "name"
            ]
            weakness_desc = content["relationships"]["weakness"]["data"]["attributes"][
                "description"
            ]
            description += "\n##Weakness: {}\n{}".format(weakness_title, weakness_desc)
        except:
            pass

        return description
