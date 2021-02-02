__guide__ = "aaronweaver"
__author__ = "Rajarshi333"


import logging
import re

from dateutil import parser
from defusedxml import ElementTree

from dojo.models import Finding

logger = logging.getLogger(__name__)


class FortifyXMLParser(object):
    def get_findings(self, filename, test):
        fortify_scan = ElementTree.parse(filename)
        root = fortify_scan.getroot()

        language_list = []
        # Get Date
        date_string = root.getchildren()[5].getchildren()[1].getchildren()[2].text
        date_list = date_string.split()[1:4]
        date_list = [item.replace(",", "") for item in date_list]
        date_act = ".".join(date_list)
        find_date = parser.parse(date_act)
        # Get Language
        lang_string = root[8][4][2].text
        lang_need_string = re.findall(
            "^.*com.fortify.sca.Phase0HigherOrder.Languages.*$",
            lang_string,
            re.MULTILINE,
        )
        lang_my_string = lang_need_string[0]
        language = lang_my_string.split("=")[1]
        if language not in language_list:
            language_list.append(language)

        # Get Category Information:
        # Abstract, Explanation, Recommendation, Tips
        cat_meta = {}
        # Get all issues
        issues = []
        meta_pair = ({}, {})
        issue_pair = ([], [])
        for ReportSection in root.findall("ReportSection"):
            if ReportSection.findtext("Title") in [
                "Results Outline",
                "Issue Count by Category",
            ]:
                place = 0 if ReportSection.findtext("Title") == "Results Outline" else 1
                # Get information on the vulnerability like the Abstract, Explanation,
                # Recommendation, and Tips
                for group in ReportSection.iter("GroupingSection"):
                    title = group.findtext("groupTitle")
                    maj_attr_summary = group.find("MajorAttributeSummary")
                    if maj_attr_summary:
                        meta_info = maj_attr_summary.findall("MetaInfo")
                        meta_pair[place][title] = {
                            x.findtext("Name"): x.findtext("Value") for x in meta_info
                        }
                # Collect all issues
                for issue in ReportSection.iter("Issue"):
                    issue_pair[place].append(issue)

        if len(issue_pair[0]) > len(issue_pair[1]):
            issues = issue_pair[0]
            cat_meta = meta_pair[0]
        else:
            issues = issue_pair[1]
            cat_meta = meta_pair[1]

        # All issues obtained, create a map for reference
        issue_map = {}
        issue_id = "N/A"
        try:
            for issue in issues:
                issue_id = issue.attrib["iid"]
                details = {
                    "Category": issue.find("Category").text,
                    "Folder": issue.find("Folder").text,
                    "Kingdom": issue.find("Kingdom").text,
                    "Abstract": issue.find("Abstract").text,
                    "Friority": issue.find("Friority").text,
                    "FileName": issue.find("Primary").find("FileName").text,
                    "FilePath": issue.find("Primary").find("FilePath").text,
                    "LineStart": issue.find("Primary").find("LineStart").text,
                }

                if issue.find("Primary").find("Snippet"):
                    details["Snippet"] = issue.find("Primary").find("Snippet").text
                else:
                    details["Snippet"] = "n/a"

                if issue.find("Source"):
                    source = {
                        "FileName": issue.find("Source").find("FileName").text,
                        "FilePath": issue.find("Source").find("FilePath").text,
                        "LineStart": issue.find("Source").find("LineStart").text,
                        "Snippet": issue.find("Source").find("Snippet").text,
                    }
                    details["Source"] = source

                issue_map.update({issue.attrib["iid"]: details})
        except AttributeError:
            logger.warning("XML Parsing error on issue number: %s", issue_id)
            raise
        # map created

        items = []
        dupes = set()
        for issue_key, issue in issue_map.items():
            title = self.format_title(
                issue["Category"], issue["FileName"], issue["LineStart"]
            )
            if title not in dupes:
                items.append(
                    Finding(
                        title=title,
                        severity=issue["Friority"],
                        numerical_severity=Finding.get_numerical_severity(
                            issue["Friority"]
                        ),
                        file_path=issue["FilePath"],
                        line_number=int(issue["LineStart"]),
                        line=int(issue["LineStart"]),
                        static_finding=True,
                        active=False,
                        verified=False,
                        test=test,
                        date=find_date,
                        description=self.format_description(issue, cat_meta),
                        mitigation=self.format_mitigation(issue, cat_meta),
                        unique_id_from_tool=issue_key,
                    )
                )
                dupes.add(title)
        return items

    def format_title(self, category, filename, line_no):
        """
        Builds the title much like it is represented in Fortify
        :param category: Basically the title of the issue in the code
        :param filename: File where it is found
        :param line_no:  Line number of offending line
        :return: str
        """
        return "{} - {}: {}".format(category, filename, line_no)

    def format_mitigation(self, issue, meta_info) -> str:
        """
        Built from the meta_info of a category. All items of the same category will
        have the same information in it
        :param issue:  Issue dictionary
        :param meta_info:  Meta_info dictionary
        :return: str
        """
        mitigation = ""
        recommendation = meta_info[issue["Category"]].get("Recommendations")
        if recommendation:
            mitigation += "###Recommendation:\n {}\n".format(recommendation)

        tips = meta_info[issue["Category"]].get("Tips")
        if tips:
            mitigation += "###Tips:\n {}".format(tips)
        return mitigation

    def format_description(self, issue, meta_info) -> str:
        """
        Returns a formatted Description. This will contain information about the category,
        snippet from the code, including the file and line number. If there is source information
        it will also include that. Adds explanation of finding from the meta info
        :param issue:       Issue Dictionary
        :param meta_info:   Meta Dictionary
        :return: str
        """
        desc = "##Catagory: {}\n".format(issue["Category"])
        desc += (
            "###Abstract:\n{}\n###Snippet:\n**File: {}: {}**\n```\n{}\n```\n".format(
                issue["Abstract"],
                issue["FileName"],
                issue["LineStart"],
                issue["Snippet"],
            )
        )
        explanation = meta_info[issue["Category"]].get("Explanation")
        source = issue.get("Source")
        if source:
            desc += (
                "##Source:\nThis snippet provides more context on the execution path that "
                "leads to this finding. \n"
                "####Snippet:\n**File: {}: {}**\n```\n{}\n```\n".format(
                    source["FileName"], source["LineStart"], source["Snippet"]
                )
            )
        if explanation:
            desc += "##Explanation:\n {}".format(explanation)
        return desc
