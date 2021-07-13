""" Surely a fragile parser, but gets things started and will evolve over time I guess.
It seems that a lot of the json data does not have any securityData data
So these are just skipped, since there is nothing much to do with them here
"""
import json

from dojo.models import Finding


class SonatypeParser(object):
    # This parser does not deal with licenses information.

    def get_scan_types(self):
        return ["Sonatype Application Scan"]

    def get_label_for_scan_types(self, scan_type):
        return scan_type  # no custom label for now

    def get_description_for_scan_types(self, scan_type):
        return "Can be imported in JSON format"

    def get_findings(self, json_output, test):
        tree = json.load(json_output)
        return self.get_items(tree, test)

    def get_items(self, tree, test):
        items = {}
        if 'components' in tree:
            vulnerability_tree = tree['components']

            for node in vulnerability_tree:
                item = get_item(node, test)
                if item is None:
                    continue
                # TODO
                unique_key = node['hash']
                items[unique_key] = item

        return list(items.values())


def get_item(vulnerability, test):
    # Following the CVSS Scoring per https://nvd.nist.gov/vuln-metrics/cvss
    if vulnerability['securityData'] is not None and len(vulnerability['securityData']['securityIssues']) >= 1:
        # there can be nothing in the array, or securityData can be null altogether. If the latter, well, nothing much to do?
        # issues is an array, and there can be 2+ of them, e.g. a cve and a sonatype entry or two cves
        # Given the current Finding class, if a cve, will be the main. If not a cve, then CVE ref will remain null due to regex.
        # Others go to references.
        main_finding = vulnerability['securityData']['securityIssues'][0]

        if main_finding.get("source") == "cve":
            cve = main_finding.get("reference")
        else:
            # if sonatype of else, will not match Finding model today
            cve = None

        if main_finding['severity'] <= 3.9:
            severity = "Low"
        elif main_finding['severity'] > 4.0 and main_finding['severity'] <= 6.9:
            severity = "Medium"
        elif main_finding['severity'] and main_finding['severity'] <= 8.9:
            severity = "High"
        else:
            severity = "Critical"

        references = []
        if len(vulnerability['securityData']['securityIssues']) > 1:
            for additional_issue in vulnerability['securityData']['securityIssues']:
                references.append("{}, {}, {}, {}, {} ".format(
                    additional_issue.get("reference"),
                    additional_issue.get("status"),
                    additional_issue.get("severity"),
                    additional_issue.get("threatCategory"),
                    additional_issue.get("url"))
                )

        component_id = ''
        if 'componentIdentifier' in vulnerability:
            if vulnerability['componentIdentifier']['format'] == "maven":
                component_id = "{} {} {}".format(
                    vulnerability['componentIdentifier']['coordinates']['artifactId'],
                    vulnerability['componentIdentifier']['coordinates']['groupId'],
                    vulnerability['componentIdentifier']['coordinates']['version']
                )
            elif vulnerability['componentIdentifier']['format'] == "a-name":
                component_id = "{} {} {}".format(
                    vulnerability['componentIdentifier']['coordinates']['name'],
                    vulnerability['componentIdentifier']['coordinates']['qualifier'],
                    vulnerability['componentIdentifier']['coordinates']['version']
                )

        finding_title = "{} - {}".format(
            main_finding['reference'],
            component_id
        )

        finding_description = "Hash {}\n\n".format(vulnerability['hash'])
        finding_description += component_id
        finding_description += "\n\nPlease check the CVE details of this finding for a detailed description. The details of issues beginning with \"SONATYPE-\" can be found by contacting Sonatype, Inc. or through mechanisms they have provided in their product."
        threat_category = main_finding.get("threatCategory", "CVSS vector not provided. ").title()
        status = main_finding['status']
        score = main_finding.get('severity', "No CVSS score yet.")
        if 'pathnames' in vulnerability:
            file_path = ' '.join(vulnerability['pathnames'])[:1000]
        else:
            file_path = ''

        # create the finding object
        finding = Finding(
            title=finding_title,
            cve=cve,
            cvssv3_score=score,
            test=test,
            severity=severity,
            description=finding_description,
            mitigation=status,
            references="{}\n{}\n".format(main_finding['url'], "\n".join(references)),
            false_p=False,
            duplicate=False,
            out_of_scope=False,
            mitigated=None,
            file_path=file_path,
            impact=threat_category,
            static_finding=True
        )

        finding.description = finding.description.strip()

        return finding
    else:
        return None
