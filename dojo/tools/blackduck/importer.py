import csv
import io
import re
import zipfile
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .model import BlackduckFinding


class Importer(ABC):
    @abstractmethod
    def parse_findings(self, report: Path) -> Iterable[BlackduckFinding]:
        while False:
            yield None


class BlackduckImporter(Importer):
    def parse_findings(self, report: Path) -> Iterable[BlackduckFinding]:
        if not issubclass(type(report), Path):
            report = Path(report.temporary_file_path())

        try:
            if zipfile.is_zipfile(str(report)):
                return self._process_zipfile(report)
            else:
                return self._process_csvfile(report)
        except Exception as e:
            print("Error processing file: {}".format(e))

    def _process_csvfile(self, report):
        """
        If passed in a regular security.csv, process it.
        No file information then.
        """
        security_issues = dict()
        try:
            with open(str(report), "r") as f:
                security_issues = self.__partition_by_key(f)

        except Exception as e:
            print("Could not process csv file: {}".format(e))

        project_ids = set(security_issues.keys())
        return self._process_project_findings(project_ids, security_issues, None)

    def _process_zipfile(self, report):
        """
        Will take a zip file, look for security.csv and files.csv and union them on project id.
        This allows to have the file component for a vulnerability.
        """
        files = dict()
        security_issues = dict()
        try:
            with zipfile.ZipFile(str(report)) as zip:
                for full_file_name in zip.namelist():
                    file_name = full_file_name.split("/")[-1]
                    # Backwards compatibility, newer versions of Blackduck have a source file rather
                    # than a "files" file.
                    if "source" in file_name or "files" in file_name:
                        with io.TextIOWrapper(zip.open(full_file_name)) as f:
                            files = self.__partition_by_key(f)
                    elif "security" in file_name:
                        with io.TextIOWrapper(zip.open(full_file_name)) as f:
                            security_issues = self.__partition_by_key(f)

        except Exception as e:
            print("Could not process zip file: {}".format(e))

        project_ids = set(files.keys()) & set(security_issues.keys())
        return self._process_project_findings(project_ids, security_issues, files)

    def _process_project_findings(self, project_ids, security_issues, files=None):
        """
        Process findings per projects and return a BlackduckFinding object per the model
        """
        for project_id in project_ids:
            locations = set()
            if files is not None:
                for file_entry in files[project_id]:
                    file_entry_dict = dict(file_entry)
                    path = file_entry_dict.get("Path")
                    archive_context = file_entry_dict.get("Archive context")
                    if archive_context:
                        full_path = "{}{}".format(archive_context, path[1:])
                    else:
                        full_path = path

                    # 4000 character limit on this field
                    total_len = len(full_path)
                    for location in list(locations):
                        # + 2 for the ", " that will be added.
                        total_len += len(location) + 2
                    if total_len < 4000:
                        locations.add(full_path)
                    else:
                        break

            for issue in security_issues[project_id]:
                security_issue_dict = dict(issue)
                cve = self.get_cve(security_issue_dict.get("Vulnerability id")).upper()
                location = ", ".join(locations)

                yield BlackduckFinding(
                    cve,
                    security_issue_dict.get("Description"),
                    security_issue_dict.get("Security Risk"),
                    security_issue_dict.get("Impact"),
                    security_issue_dict.get("Project name"),
                    security_issue_dict.get("Version"),
                    security_issue_dict.get("Vulnerability source"),
                    security_issue_dict.get("URL"),
                    security_issue_dict.get("Channel version origin id"),
                    security_issue_dict.get("Component origin id"),
                    security_issue_dict.get("Published on"),
                    security_issue_dict.get("Updated on"),
                    security_issue_dict.get("Base score"),
                    security_issue_dict.get("Exploitability"),
                    security_issue_dict.get("Remediation status"),
                    security_issue_dict.get("Remediation target date"),
                    security_issue_dict.get("Remediation actual date"),
                    security_issue_dict.get("Remediation comment"),
                    location,
                )

    def __partition_by_key(self, csv_file):
        records = csv.DictReader(csv_file)
        findings = defaultdict(set)
        # Backwards compatibility. Newer versions of Blackduck use Component id.
        if "Project id" in records.fieldnames:
            key = "Project id"
        else:
            key = "Component id"
        for record in records:
            findings[record.get(key)].add(frozenset(record.items()))
        return findings

    def get_cve(self, vuln_id):
        cve_search = re.search(r"CVE-\d{4}-\d{4,9}", vuln_id, re.IGNORECASE)
        return cve_search.group(0) if cve_search else vuln_id
