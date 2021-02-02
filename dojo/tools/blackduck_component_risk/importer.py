import csv
import io
import zipfile
from pathlib import Path

__author__ = "Apipia"


class BlackduckCRImporter(object):
    """
    Importer for blackduck. V3 is different in that it creates a Finding in defect dojo
    for each vulnerable component version used in a project, for each license that is
    In Violation for the components, AND for each license that is marked with a 'License Risk'
    that is anything other than 'OK' as a For Review Finding in defect dojo.
    Security Risks and License Risks.
    Security Risks have the severity and impact of it's highest vulnerability the component has.
    """

    def parse_findings(self, report: Path) -> (dict, dict, dict):
        """
        Given a path to a zip file, this function will find the relevant CSV files and
        return three dictionaries with the information needed. Dictionaries are components, source and
        security risks.
        :param report: Path to zip file
        :return: ( {component_id:details} , {component_id:[vulns]}, {component_id:[source]} )
        """
        if not issubclass(type(report), Path):
            report = Path(report.temporary_file_path())
        try:
            if zipfile.is_zipfile(str(report)):
                return self._process_zipfile(report)
            else:
                raise Exception("File not a zip!")
        except Exception as e:
            print("Error processing file: {}".format(e))

    def _process_zipfile(self, report: Path) -> (dict, dict, dict):
        """
        Open the zip file and extract information on vulnerable packages from security.csv,
        as well as license risk information from components.csv, and location/context from source.csv.
        :param report: the file
        :return: (dict, dict, dict)
        """
        components = dict()
        source = dict()
        try:
            with zipfile.ZipFile(str(report)) as zip:
                c_file = False
                s_file = False
                src_file = False
                for full_file_name in zip.namelist():
                    # Just in case the word component or security is in the name of
                    # zip file, best to ignore it.
                    file_name = full_file_name.split("/")[-1]
                    # Look for the component and security CSVs.
                    if "component" in file_name:
                        with io.TextIOWrapper(zip.open(full_file_name)) as f:
                            components = self.__get_components(f)
                            c_file = True
                    elif "security" in file_name:
                        with io.TextIOWrapper(zip.open(full_file_name)) as f:
                            security_issues = self.__get_security_risks(f)
                            s_file = True
                    elif "source" in file_name:
                        with io.TextIOWrapper(zip.open(full_file_name)) as f:
                            source = self.__get_source(f)
                            src_file = True
                # Raise exception to error-out if the zip is missing either of these files.
                if not (c_file and s_file):
                    raise Exception("Zip file missing needed files!")

        except Exception as e:
            print("Could not process zip file: {}".format(e))

        return components, security_issues, source

    def __get_source(self, src_file) -> dict:
        """
        Builds a dictionary to reference source location data for components.
        Each component is represented to match the component dictionary
        {
            "component_id:version_id":
                {"column1":"value", "column2":"value", ...},
            ...
        }
        Each row in the CSV will be a unique entry.
        :param src_file: File object of the source.csv
        :return: {str:dct}
        """
        source = {}
        records = csv.DictReader(src_file)
        for record in records:
            # Using component_id:version_id for unique identifier of each component
            source[
                record.get("Component id") + ":" + record.get("Version id") + ":License"
            ] = {x[0]: x[1] for x in record.items()}
        return source

    def __get_components(self, csv_file) -> dict:
        """
        Builds a dictionary to reference components.
        Each component is represented
        {
            "component_id:version_id":
                {"column1":"value", "column2":"value", ...},
            ...
        }
        Each row in the CSV will be a unique entry.
        :param csv_file: File object of the component.csv
        :return: {str:dict}
        """
        components = {}
        records = csv.DictReader(csv_file)
        for record in records:
            # Using component_id:version_id for unique identifier of each component
            components[
                record.get("Component id") + ":" + record.get("Version id") + ":License"
            ] = {x[0]: x[1] for x in record.items()}
        return components

    def __get_security_risks(self, csv_file) -> dict:
        """
        Creates a dictionary to represent vulnerabilities in a given component. Each entry in the
        dictionary is represented:
        {
            "component_id:version_id":
                [{vuln_column1: value, vuln_column2: value, ...},{...}]
        }
        Each entry is a component with the id:version_id as a key, and a list of vulnerabilities
        as the value.
        :param csv_file:
        :return: {component:[vulns]}
        """
        securities = {}
        records = csv.DictReader(csv_file)
        for record in records:
            key = (
                record.get("Component id")
                + ":"
                + record.get("Version id")
                + ":security"
            )
            vulns = securities.get(key) or []
            vulns.append({x[0]: x[1] for x in record.items()})
            securities[key] = vulns
        return securities
