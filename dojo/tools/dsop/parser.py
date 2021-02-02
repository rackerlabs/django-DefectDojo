import re

import pandas as pd

from dojo.models import Finding

__author__ = "Matt Sicker"


class DsopParser:
    def get_findings(self, file, test):
        items = list()
        f = pd.ExcelFile(file)
        self.__parse_disa(
            pd.read_excel(
                f,
                sheet_name="OpenSCAP - DISA Compliance",
                parse_dates=["scanned_date"],
                dtype={"result": "category", "severity": "category"},
            ),
            test,
            items,
        )
        self.__parse_oval(
            pd.read_excel(f, sheet_name="OpenSCAP - OVAL Results"), test, items
        )
        self.__parse_twistlock(
            pd.read_excel(
                f,
                sheet_name="Twistlock Vulnerability Results",
                dtype={"severity": "category"},
            ),
            test,
            items,
        )
        self.__parse_anchore(
            pd.read_excel(
                f, sheet_name="Anchore CVE Results", dtype={"severity": "category"}
            ),
            test,
            items,
        )
        self.__parse_anchore_compliance(
            pd.read_excel(
                f,
                sheet_name="Anchore Compliance Results",
                dtype={"severity": "category"},
            ),
            test,
            items,
        )
        return items

    def __parse_disa(self, df: pd.DataFrame, test, items):
        for row in df.itertuples(index=False):
            if row.result not in ("fail", "notchecked"):
                continue
            title = row.title
            unique_id = row.ruleid
            if row.severity == "unknown":
                severity = "Info"
            else:
                severity = row.severity.title()
            cve = row.identifiers
            references = row.refs
            description = row.desc
            impact = row.rationale
            date = row.scanned_date.date()
            tags = "disa"

            finding = Finding(
                title=title,
                date=date,
                cve=cve,
                severity=severity,
                description=description,
                impact=impact,
                references=references,
                test=test,
                unique_id_from_tool=unique_id,
                static_finding=True,
                dynamic_finding=False,
            )
            finding.unsaved_tags = tags
            items.append(finding)

    def __parse_oval(self, df: pd.DataFrame, test, items):
        severity_pattern = re.compile(r"\((.*)\)")
        for row in df.itertuples(index=False):
            if not row.result or row.result in ("false"):
                continue
            title = row.title
            match = severity_pattern.search(title)
            if match:
                sev = match.group(1)
                if sev == "Important":
                    severity = "High"
                elif sev == "Moderate":
                    severity = "Medium"
                elif sev == "None":
                    severity = "Info"
                else:
                    severity = sev
            else:
                severity = "Info"
            unique_id = row.id
            cve = row.ref
            tags = "oval"

            finding = Finding(
                title=title,
                cve=cve,
                severity=severity,
                unique_id_from_tool=unique_id,
                test=test,
                static_finding=True,
                dynamic_finding=False,
            )
            finding.unsaved_tags = tags
            items.append(finding)

    def __parse_twistlock(self, df: pd.DataFrame, test, items):
        for row in df.itertuples(index=False):
            cve = row.id
            description = row.desc
            mitigation = row.status
            url = row.link
            component_name = row.packageName
            component_version = row.packageVersion
            title = "{}: {} - {}".format(cve, component_name, component_version)
            if row.severity == "important":
                severity = "High"
            elif row.severity == "moderate":
                severity = "Medium"
            else:
                severity = row.severity.title()
            severity_justification = row.vecStr
            tags = "twistlock"

            finding = Finding(
                title=title,
                cve=cve,
                url=url,
                severity=severity,
                description=description,
                component_name=component_name,
                component_version=component_version,
                severity_justification=severity_justification,
                test=test,
                static_finding=True,
                dynamic_finding=False,
            )
            finding.unsaved_tags = tags
            items.append(finding)

    def __parse_anchore(self, df: pd.DataFrame, test, items):
        for row in df.itertuples(index=False):
            cve = row.cve
            severity = row.severity
            component = row.package
            file_path = row.package_path
            mitigation = row.fix
            description = "Image affected: {}".format(row.tag)
            title = "{}: {}".format(cve, component)
            tags = "anchore"

            finding = Finding(
                title=title,
                cve=cve,
                severity=severity,
                mitigation=mitigation,
                component_name=component,
                description=description,
                test=test,
                static_finding=True,
                dynamic_finding=False,
                file_path=file_path,
            )
            finding.unsaved_tags = tags
            items.append(finding)

    def __parse_anchore_compliance(self, df: pd.DataFrame, test, items):
        for row in df.itertuples(index=False):
            if row.policy_id != "DoDFileChecks":
                continue

            if row.gate_action == "warn":
                severity = "Medium"
            elif row.gate_action == "stop":
                severity = "Critical"
            else:
                severity = "Info"
            severity = severity
            mitigation = "To be investigated"
            description = "Gate: {} (Trigger: {}): {}".format(
                row.gate, row.trigger, row.check_output
            )
            title = "{}: {}".format(row.policy_id, row.trigger_id)
            tags = "anchore_compliance"

            finding = Finding(
                title=title,
                severity=severity,
                mitigation=mitigation,
                description=description,
                test=test,
                static_finding=True,
                dynamic_finding=False,
            )
            finding.unsaved_tags = tags
            items.append(finding)
