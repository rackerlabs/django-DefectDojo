__author__ = 'bakalor'
__maintainer__ = "Igor Bakalo"
__email__ = "bigorigor.ua@gmail.com"
__status__ = "Development"

import re
import html2text
from defusedxml import ElementTree as ET
from dojo.models import Finding


class SpotbugsParser(object):

    def get_scan_types(self):
        return ["SpotBugs Scan"]

    def get_label_for_scan_types(self, scan_type):
        return scan_type  # no custom label for now

    def get_description_for_scan_types(self, scan_type):
        return "XML report of textui cli."

    def get_findings(self, filename, test):
        mitigation_patterns = dict()
        reference_patterns = dict()
        dupes = dict()

        SEVERITY = {
            '1': 'High',
            '2': 'Medium',
            '3': 'Low'
        }

        tree = ET.parse(filename)
        root = tree.getroot()

        html_parser = html2text.HTML2Text()
        html_parser.ignore_links = False

        # Parse <BugPattern> tags
        for pattern in root.findall('BugPattern'):
            # Parse <BugPattern>...<Details> html content
            html_text = html_parser.handle(
                ET.tostring(
                    pattern.find('Details'),
                    method='text'
                ).decode('utf-8')
            )

            # Parse mitigation from html
            mitigation = ''
            i = 0
            for line in html_text.splitlines():
                i += 1
                # Break loop when references are reached
                if 'Reference' in line:
                    break
                # Add a string before the code indicating that it's just an example, NOT the actual scanned code
                if ('Vulnerable Code:' in line) or ('Insecure configuration:' in line) or ('Code at risk:' in line):
                    mitigation += '\n\n#### Example\n'
                # Add line to mitigation
                mitigation += line + '\n'
            # Add mitigations to dictionary
            mitigation_patterns[pattern.get('type')] = mitigation

            # Parse references from html
            reference = ''
            #   Sometimes there's a breakline in the middle of the reference,
            #   so the splitlines method ends up breaking it in two.
            #   We solve this problem by joining all references and adding breaklines with regex.
            # Start loop where the previous loop ended
            for line in html_text.splitlines()[i:]:
                # Concatenate all references in one big string
                reference += line + ' '
            # Add breakline between each reference
            #   regex: turns ')  [' into ')\n['
            #      ')': reference ends
            #      '[': reference starts
            reference = re.sub(r'(?<=\))(.*?)(?=\[)', '\n', reference)
            # Add references to dictionary
            reference_patterns[pattern.get('type')] = reference

        # Parse <BugInstance> tags
        for bug in root.findall('BugInstance'):
            desc = ''
            for message in bug.itertext():
                desc += message + '\n'

            dupe_key = bug.get('instanceHash')

            title = bug.find('ShortMessage').text
            cwe = bug.get('cweid', default=0)
            severity = SEVERITY[bug.get('priority')]
            description = desc
            mitigation = mitigation_patterns[bug.get('type')]
            references = reference_patterns[bug.get('type')]

            # find the source line and file on the buginstance
            source_line = None
            source_file = "N/A"

            source_extract = bug.find('SourceLine')
            if source_extract is not None:
                source_file = source_extract.get("sourcepath")
                if 'start' in source_extract and source_extract["start"].isdigit():
                    source_line = int(source_extract["start"])

            if dupe_key in dupes:
                finding = dupes[dupe_key]
            else:
                finding = Finding(
                    title=title,
                    cwe=cwe,
                    severity=severity,
                    description=description,
                    mitigation=mitigation,
                    references=references,
                    test=test,
                    static_finding=True,
                    line=source_line,
                    file_path=source_file,
                    sast_source_line=source_line,
                    sast_source_file_path=source_file
                )
                dupes[dupe_key] = finding

        return list(dupes.values())
