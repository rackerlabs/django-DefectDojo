import logging
import re

from django.utils.html import strip_tags
from lxml import etree

from dojo.models import Finding

logger = logging.getLogger(__name__)


class SonarQubeHtmlParser(object):
    def get_findings(self, filename, test, mode=None):
        parser = etree.HTMLParser()
        tree = etree.parse(filename, parser)
        if mode not in [None, "detailed"]:
            raise ValueError(
                "Internal error: Invalid mode "
                + mode
                + ". Expected: one of None, 'detailed'"
            )

        return self.get_items(tree, test, mode)

    def get_items(self, tree, test, mode):
        # Check that there is at least one vulnerability (the vulnerabilities table is absent when no vuln are found)
        detailTbody = tree.xpath(
            "/html/body/div[contains(@class,'detail')]/table/tbody"
        )
        dupes = dict()
        if len(detailTbody) == 2:
            # First is "Detail of the Detected Vulnerabilities" (not present if no vuln)
            # Second is "Known Security Rules"
            vulnerabilities_table = list(detailTbody[0].iter("tr"))
            rules_table = list(detailTbody[1].xpath("tr"))

            # iterate over the rules once to get the information we need
            rulesDic = dict()
            for rule in rules_table:
                rule_properties = list(rule.iter("td"))
                rule_name = list(rule_properties[0].iter("a"))[0].text
                rule_details = list(rule_properties[1].iter("details"))[0]
                rulesDic[rule_name] = rule_details

            for vuln in vulnerabilities_table:
                vuln_properties = list(vuln.iter("td"))
                vuln_rule_name = list(vuln_properties[0].iter("a"))[0].text
                vuln_severity = self.convert_sonar_severity(vuln_properties[1].text)
                vuln_file_path = vuln_properties[2].text
                vuln_line = vuln_properties[3].text
                vuln_title = vuln_properties[4].text
                vuln_mitigation = vuln_properties[5].text
                vuln_key = vuln_properties[6].text
                if vuln_title is None or vuln_mitigation is None:
                    raise Exception(
                        "Parser ValueError: can't find a title or a mitigation for vulnerability of name "
                        + vuln_rule_name
                    )
                try:
                    vuln_details = rulesDic[vuln_rule_name]
                    vuln_description = self.get_description(vuln_details)
                    vuln_references = self.get_references(vuln_rule_name, vuln_details)
                    vuln_cwe = self.get_cwe(vuln_references)
                except KeyError:
                    vuln_description = "No description provided"
                    vuln_references = ""
                    vuln_cwe = 0
                if mode is None:
                    self.process_result_file_name_aggregated(
                        test,
                        dupes,
                        vuln_title,
                        vuln_cwe,
                        vuln_description,
                        vuln_file_path,
                        vuln_line,
                        vuln_severity,
                        vuln_mitigation,
                        vuln_references,
                    )
                else:
                    self.process_result_detailed(
                        test,
                        dupes,
                        vuln_title,
                        vuln_cwe,
                        vuln_description,
                        vuln_file_path,
                        vuln_line,
                        vuln_severity,
                        vuln_mitigation,
                        vuln_references,
                        vuln_key,
                    )
        return list(dupes.values())

    # Process one vuln from the report for "SonarQube Scan detailed"
    # Create the finding and add it into the dupes list
    def process_result_detailed(
        self,
        test,
        dupes,
        vuln_title,
        vuln_cwe,
        vuln_description,
        vuln_file_path,
        vuln_line,
        vuln_severity,
        vuln_mitigation,
        vuln_references,
        vuln_key,
    ):
        # vuln_key is the unique id from tool which means that there is basically no aggregation except real duplicates
        aggregateKeys = "{}{}{}{}{}".format(
            vuln_cwe, vuln_title, vuln_description, vuln_file_path, vuln_key
        )
        find = Finding(
            title=vuln_title,
            cwe=int(vuln_cwe),
            description=vuln_description,
            file_path=vuln_file_path,
            line=vuln_line,
            test=test,
            severity=vuln_severity,
            mitigation=vuln_mitigation,
            references=vuln_references,
            active=False,
            verified=False,
            false_p=False,
            duplicate=False,
            out_of_scope=False,
            mitigated=None,
            impact="No impact provided",
            numerical_severity=Finding.get_numerical_severity(vuln_severity),
            static_finding=True,
            dynamic_finding=False,
            unique_id_from_tool=vuln_key,
        )
        dupes[aggregateKeys] = find

    # Process one vuln from the report for "SonarQube Scan"
    # Create the finding and add it into the dupes list
    # For aggregated findings:
    #  - the description is enriched with each finding line number
    #  - the mitigation (message) is concatenated with each finding's mitigation value
    def process_result_file_name_aggregated(
        self,
        test,
        dupes,
        vuln_title,
        vuln_cwe,
        vuln_description,
        vuln_file_path,
        vuln_line,
        vuln_severity,
        vuln_mitigation,
        vuln_references,
    ):
        aggregateKeys = "{}{}{}{}".format(
            vuln_cwe, vuln_title, vuln_description, vuln_file_path
        )
        descriptionOneOccurence = "Line: {}".format(vuln_line)
        if aggregateKeys not in dupes:
            find = Finding(
                title=vuln_title,
                cwe=int(vuln_cwe),
                description=vuln_description
                + "\n\n-----\nOccurences:\n"
                + descriptionOneOccurence,
                file_path=vuln_file_path,
                # No line number because we have aggregated different vulnerabilities that may have different line numbers
                test=test,
                severity=vuln_severity,
                mitigation=vuln_mitigation,
                references=vuln_references,
                active=False,
                verified=False,
                false_p=False,
                duplicate=False,
                out_of_scope=False,
                mitigated=None,
                impact="No impact provided",
                numerical_severity=Finding.get_numerical_severity(vuln_severity),
                static_finding=True,
                dynamic_finding=False,
                nb_occurences=1,
            )
            dupes[aggregateKeys] = find
        else:
            # We have already created a finding for this aggregate: updates the description, nb_occurences and mitigation (message field in the report which may vary for each vuln)
            find = dupes[aggregateKeys]
            find.description = "{}\n{}".format(
                find.description, descriptionOneOccurence
            )
            find.mitigation = "{}\n______\n{}".format(find.mitigation, vuln_mitigation)
            find.nb_occurences = find.nb_occurences + 1

    def convert_sonar_severity(self, sonar_severity):
        sev = sonar_severity.lower()
        if sev == "blocker":
            return "Critical"
        elif sev == "critical":
            return "High"
        elif sev == "major":
            return "Medium"
        elif sev == "minor":
            return "Low"
        else:
            return "Info"

    def get_description(self, vuln_details):
        rule_description = etree.tostring(vuln_details, pretty_print=True).decode(
            "utf-8", errors="replace"
        )
        rule_description = rule_description.split("<h2>See", 1)[0]
        rule_description = (str(rule_description)).replace("<h2>", "**")
        rule_description = (str(rule_description)).replace("</h2>", "**")
        rule_description = strip_tags(rule_description).strip()
        return rule_description

    def get_references(self, rule_name, vuln_details):
        rule_references = rule_name
        for a in vuln_details.iter("a"):
            rule_references += "\n" + a.text
        return rule_references

    def get_cwe(self, vuln_references):
        # Match only the first CWE!
        cweSearch = re.search("CWE-([0-9]*)", vuln_references, re.IGNORECASE)
        if cweSearch:
            return cweSearch.group(1)
        else:
            return 0
