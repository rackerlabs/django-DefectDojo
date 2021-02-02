from datetime import datetime
from xml.dom import NamespaceErr

from lxml import etree

from dojo.models import Finding


def truncate_str(value: str, maxlen: int):
    if len(value) > maxlen:
        return value[: maxlen - 12] + " (truncated)"
    return value


# This parser is written for Veracode Detailed XML reports, version 1.5.
# Version is annotated in the report, `detailedreport/@report_format_version`.
class VeracodeXMLParser(object):
    ns = {"x": "https://www.veracode.com/schema/reports/export/1.0"}
    vc_severity_mapping = {1: "Info", 2: "Low", 3: "Medium", 4: "High", 5: "Critical"}

    def get_findings(self, filename, test):
        if filename is None:
            return list()
        try:
            xml = etree.parse(filename, etree.XMLParser(resolve_entities=False))
        except:
            raise NamespaceErr(
                "Cannot parse this report. Make sure to upload a proper Veracode Detailed XML report."
            )

        ns = self.ns
        report_node = xml.xpath("/x:detailedreport", namespaces=self.ns)[0]

        if not report_node:
            raise NamespaceErr(
                "This version of Veracode report is not supported.  "
                "Please make sure the export is formatted using the "
                "https://www.veracode.com/schema/reports/export/1.0 schema."
            )

        dupes = dict()

        # Get SAST findings
        # This assumes `<category/>` only exists with the `<severity/>` nodes.
        for category_node in report_node.xpath("//x:category", namespaces=ns):

            # Mitigation text.
            mitigation_text = ""
            mitigation_text += (
                category_node.xpath(
                    "string(x:recommendations/x:para/@text)", namespaces=ns
                )
                + "\n\n"
            )
            # Bullet list of recommendations:
            mitigation_text += "".join(
                list(
                    map(
                        lambda x: "    * " + x + "\n",
                        category_node.xpath(
                            "x:recommendations/x:para/x:bulletitem/@text", namespaces=ns
                        ),
                    )
                )
            )

            for flaw_node in category_node.xpath(
                ".//x:staticflaws/x:flaw", namespaces=ns
            ):
                dupe_key = self.__xml_flaw_to_unique_id(flaw_node)

                # Only process if we didn't do that before.
                if dupe_key not in dupes:
                    # Add to list.
                    dupes[dupe_key] = self.__xml_flaw_to_finding(
                        flaw_node, mitigation_text, test
                    )

        # Get SCA findings
        for vulnerable_lib_node in xml.xpath(
            "/x:detailedreport/x:software_composition_analysis/x:vulnerable_components"
            "/x:component[@vulnerabilities > 0]",
            namespaces=ns,
        ):
            dupe_key = self.__xml_sca_flaw_to_dupekey(vulnerable_lib_node)

            # Only process if we didn't do that before.
            if dupe_key not in dupes:
                dupes[dupe_key] = self.__xml_sca_flaw_to_finding(
                    vulnerable_lib_node, test
                )

        return list(dupes.values())

    @classmethod
    def __xml_flaw_to_unique_id(cls, xml_node):
        ns = cls.ns
        app_id = xml_node.xpath(
            "string(ancestor::x:detailedreport/@app_id)", namespaces=ns
        )
        issue_id = xml_node.attrib["issueid"]
        return "app-" + app_id + "_issue-" + issue_id

    @classmethod
    def __xml_flaw_to_severity(cls, xml_node):
        return cls.vc_severity_mapping.get(int(xml_node.attrib["severity"]), "Info")

    @classmethod
    def __xml_flaw_to_finding(cls, xml_node, mitigation_text, test):
        ns = cls.ns

        # Defaults
        finding = Finding()
        finding.test = test
        finding.mitigation = mitigation_text
        finding.verified = False
        finding.active = False
        finding.static_finding = True
        finding.dynamic_finding = False
        finding.unique_id_from_tool = cls.__xml_flaw_to_unique_id(xml_node)

        # Report values
        finding.severity = cls.__xml_flaw_to_severity(xml_node)
        finding.numerical_severity = Finding.get_numerical_severity(finding.severity)
        finding.cwe = int(xml_node.attrib["cweid"])
        finding.title = xml_node.attrib["categoryname"]
        finding.impact = "CIA Impact: " + xml_node.attrib["cia_impact"].upper()

        # Note that DD's legacy dedupe hashing uses the description field,
        # so for compatibility, description field should contain very static info.
        _description = xml_node.attrib["description"].replace(". ", ".\n")
        finding.description = _description

        _references = "None"
        if "References:" in _description:
            _references = _description[
                _description.index("References:") + 13 :
            ].replace(")  ", ")\n")
        finding.references = (
            _references
            + "\n\nVulnerable Module: "
            + xml_node.attrib["module"]
            + "\nType: "
            + xml_node.attrib["type"]
            + "\nVeracode issue ID: "
            + xml_node.attrib["issueid"]
        )

        _date_found = test.target_start
        if "date_first_occurrence" in xml_node.attrib:
            _date_found = datetime.strptime(
                xml_node.attrib["date_first_occurrence"], "%Y-%m-%d %H:%M:%S %Z"
            )
        finding.date = _date_found

        _is_mitigated = False
        _mitigated_date = None
        if (
            "mitigation_status" in xml_node.attrib
            and xml_node.attrib["mitigation_status"].lower() == "accepted"
        ):
            # This happens if any mitigation (including 'Potential false positive')
            # was accepted in VC.
            _is_mitigated = True
            raw_mitigated_date = xml_node.xpath(
                "string(.//x:mitigations/x:mitigation[last()]/@date)", namespaces=ns
            )
            if raw_mitigated_date:
                _mitigated_date = datetime.strptime(
                    raw_mitigated_date, "%Y-%m-%d %H:%M:%S %Z"
                )
            else:
                _mitigated_date = None
        finding.is_Mitigated = _is_mitigated
        finding.mitigated = _mitigated_date
        finding.active = not _is_mitigated

        # Check if it's a FP in veracode.
        # Only check in case finding was mitigated, since DD doesn't allow
        # both `verified` and `false_p` to be true, while `verified` is implied on the import
        # level, not on the finding-level.
        _false_positive = False
        if _is_mitigated:
            _remediation_status = xml_node.xpath(
                "string(@remediation_status)", namespaces=ns
            ).lower()
            if (
                "false positive" in _remediation_status
                or "falsepositive" in _remediation_status
            ):
                _false_positive = True
        finding.false_p = _false_positive

        _line_number = xml_node.xpath("string(@line)")
        finding.line = _line_number if _line_number else None
        finding.line_number = finding.line
        finding.sast_source_line = finding.line

        _source_file = xml_node.xpath("string(@sourcefile)")
        finding.file_path = _source_file if _source_file else None
        finding.sourcefile = finding.file_path
        finding.sast_source_file_path = finding.file_path

        _component = (
            xml_node.xpath("string(@module)") + ": " + xml_node.xpath("string(@scope)")
        )
        finding.component_name = (
            truncate_str(_component, 200) if _component != ": " else None
        )

        _sast_source_obj = xml_node.xpath("string(@functionprototype)")
        finding.sast_source_object = _sast_source_obj if _sast_source_obj else None

        return finding

    @classmethod
    def __xml_sca_flaw_to_dupekey(cls, xml_node):
        return (
            "sca_"
            + xml_node.attrib["vendor"]
            + xml_node.attrib["library"]
            + xml_node.attrib["version"]
        )

    @classmethod
    def __cvss_to_severity(cls, cvss):
        if cvss >= 9:
            return cls.vc_severity_mapping.get(5)
        elif cvss >= 7:
            return cls.vc_severity_mapping.get(4)
        elif cvss >= 4:
            return cls.vc_severity_mapping.get(3)
        elif cvss > 0:
            return cls.vc_severity_mapping.get(2)
        else:
            return cls.vc_severity_mapping.get(1)

    @classmethod
    def __xml_sca_flaw_to_finding(cls, xml_node, test):
        ns = cls.ns

        # Defaults
        finding = Finding()
        finding.test = test
        finding.mitigation = "Make sure to upgrade this component."
        finding.verified = False
        finding.active = False
        finding.static_finding = True
        finding.dynamic_finding = False
        finding.unique_id_from_tool = cls.__xml_sca_flaw_to_dupekey(xml_node)

        _library = xml_node.xpath("string(@library)", namespaces=ns)
        _vendor = xml_node.xpath("string(@vendor)", namespaces=ns)
        _version = xml_node.xpath("string(@version)", namespaces=ns)
        _cvss = xml_node.xpath("number(@max_cvss_score)", namespaces=ns)
        _file = xml_node.xpath("string(@file_name)", namespaces=ns)
        _file_path = xml_node.xpath(
            "string(x:file_paths/x:file_path/@value)", namespaces=ns
        )

        # Report values
        finding.severity = cls.__cvss_to_severity(_cvss)
        finding.numerical_severity = Finding.get_numerical_severity(finding.severity)
        finding.cwe = 937
        finding.title = "Vulnerable component: {0}:{1}".format(_library, _version)
        finding.component_name = _vendor + " / " + _library + ":" + _version
        finding.file_path = _file

        # Use report-date, otherwise DD doesn't
        # overwrite old matching SCA findings.
        finding.date = datetime.strptime(
            xml_node.xpath(
                "string(//x:component/ancestor::x:detailedreport/@last_update_time)",
                namespaces=ns,
            ),
            "%Y-%m-%d %H:%M:%S %Z",
        )

        _description = "This library has known vulnerabilities.\n"
        _description += "Full component path: " + _file_path + "\n"
        _description += "Vulnerabilities:\n\n"
        for vuln_node in xml_node.xpath(
            "x:vulnerabilities/x:vulnerability", namespaces=ns
        ):
            _description += (
                "**CVE: [{0}](https://nvd.nist.gov/vuln/detail/{0})** ({1})\n"
                "CVS Score: {2} ({3})\n"
                "Summary: \n>{4}"
                "\n\n-----\n\n".format(
                    vuln_node.xpath("string(@cve_id)", namespaces=ns),
                    datetime.strptime(
                        vuln_node.xpath("string(@first_found_date)", namespaces=ns),
                        "%Y-%m-%d %H:%M:%S %Z",
                    ).strftime("%Y/%m"),
                    vuln_node.xpath("string(@cvss_score)", namespaces=ns),
                    cls.vc_severity_mapping.get(
                        int(vuln_node.xpath("string(@severity)", namespaces=ns)), "Info"
                    ),
                    vuln_node.xpath("string(@cve_summary)", namespaces=ns),
                )
            )
        finding.description = _description

        return finding
