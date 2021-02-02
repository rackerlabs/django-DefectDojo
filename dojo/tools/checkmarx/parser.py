__author__ = "aaronweaver"

import logging
import ntpath

from dateutil import parser
from defusedxml import ElementTree

from dojo.models import Finding
from dojo.utils import add_language

logger = logging.getLogger(__name__)

# ----------------------------------------
# Structure of the checkmarx xml report:
# ----------------------------------------
# - Query:
#    the kind of vulnerabilities. Contains for example cweId
# - Result: One vulnerability in checkmarx = 1 pathId
#    Includes filename and linenumber from source of vulnerability (start of the attack vector)
# - Path: There should be only one.Parent tag of Pathnodes
# - Pathnode: all the calls from the source (start) to the sink (end) of the attack vector


class CheckmarxXMLParser(object):
    language_list = []
    mode = None
    test = None
    mitigation = "N/A"
    impact = "N/A"
    references = ""

    # mode:
    # None (default): aggregates vulnerabilites per sink filename (legacy behavior)
    # 'detailed' : No aggregation
    def get_findings(self, filename, test, mode=None):
        cxscan = ElementTree.parse(filename)
        self.test = test
        root = cxscan.getroot()
        if mode in [None, "detailed"]:
            self.mode = mode
        else:
            raise Exception(
                "Internal error: Invalid mode "
                + mode
                + ". Expected: one of None, 'detailed'"
            )

        # Dictonary to hold the aggregated findings with:
        #  - key: the concatenated aggregate keys
        #  - value: the finding
        dupes = dict()
        for query in root.findall("Query"):
            name, cwe, categories = self.getQueryElements(query)
            language = ""
            findingdetail = ""
            group = ""
            find_date = parser.parse(root.get("ScanStart"))

            if query.get("Language") is not None:
                language = query.get("Language")

            if query.get("group") is not None:
                group = query.get("group").replace("_", " ")

            for result in query.findall("Result"):
                if categories is not None:
                    findingdetail = "{}**Category:** {}\n".format(
                        findingdetail, categories
                    )

                if language is not None:
                    findingdetail = "{}**Language:** {}\n".format(
                        findingdetail, language
                    )
                    if language not in self.language_list:
                        self.language_list.append(language)

                if group is not None:
                    findingdetail = "{}**Group:** {}\n".format(findingdetail, group)

                if result.get("Status") is not None:
                    findingdetail = "{}**Status:** {}\n".format(
                        findingdetail, result.get("Status")
                    )

                deeplink = "[{}]({})".format(
                    result.get("DeepLink"), result.get("DeepLink")
                )
                findingdetail = "{}**Finding Link:** {}\n\n".format(
                    findingdetail, deeplink
                )

                if self.mode is None:
                    self.process_result_file_name_aggregated(
                        dupes, findingdetail, query, result, find_date
                    )
                elif self.mode == "detailed":
                    self.process_result_detailed(
                        dupes, findingdetail, query, result, find_date
                    )
                findingdetail = ""

        for lang in self.language_list:
            add_language(test.engagement.product, lang)

        return list(dupes.values())

    # Process one result = one pathId for default "Checkmarx Scan"
    # Create the finding and add it into the dupes list
    # If a vuln with the same file_path was found before, updates the description
    def process_result_file_name_aggregated(
        self, dupes, findingdetail, query, result, find_date
    ):
        name, cwe, categories = self.getQueryElements(query)
        titleStart = query.get("name").replace("_", " ")
        description, lastPathnode = self.get_description_file_name_aggregated(
            query, result
        )
        sinkFilename = lastPathnode.find("FileName").text
        title = "{} ({})".format(titleStart, ntpath.basename(sinkFilename))
        false_p = result.get("FalsePositive")
        aggregateKeys = "{}{}{}{}".format(categories, cwe, name, sinkFilename)

        if not (aggregateKeys in dupes):
            sev = result.get("Severity")
            find = Finding(
                title=title,
                cwe=int(cwe),
                test=self.test,
                active=False,
                verified=False,
                # this may be overwritten later by another member of the aggregate, see "else" below
                false_p=(false_p == "True"),
                # Concatenates the query information with this specific finding information
                description=findingdetail + "-----\n" + description,
                severity=sev,
                numerical_severity=Finding.get_numerical_severity(sev),
                mitigation=self.mitigation,
                impact=self.impact,
                references=self.references,
                file_path=sinkFilename,
                # No line number because we have aggregated different vulnerabilities that may have different line numbers
                url="N/A",
                date=find_date,
                static_finding=True,
                nb_occurences=1,
            )
            dupes[aggregateKeys] = find
        else:
            # We have already created a finding for this aggregate: updates the description and the nb_occurences
            find = dupes[aggregateKeys]
            find.description = "{}\n-----\n{}".format(find.description, description)
            find.nb_occurences = find.nb_occurences + 1
            # If at least one of the findings in the aggregate is exploitable, the defectdojo finding should not be "false positive"
            if false_p == "False":
                dupes[aggregateKeys].false_p = False

    # Iterate over function calls / assignments to extract finding description and last pathnode
    def get_description_file_name_aggregated(self, query, result):
        description = ""

        # Loop over <Path> (there should be only one)
        for path in result.findall("Path"):
            firstPathnode = True
            for pathnode in path.findall("PathNode"):
                if firstPathnode:
                    (
                        sourceFilename,
                        sourceLineNumber,
                        sourceObject,
                    ) = self.get_pathnode_elements(pathnode)
                    firstPathnode = False
        # At this point we have iterated over all path nodes (function calls) and pathnode is at the sink of the vulnerability
        sinkFilename, sinkLineNumber, sinkObject = self.get_pathnode_elements(pathnode)
        description = "<b>Source filename: </b>{}\n<b>Source line number: </b> {}\n<b>Source object: </b> {}".format(
            sourceFilename, sourceLineNumber, sourceObject
        )
        description = "{}\n\n<b>Sink filename: </b>{}\n<b>Sink line number: </b> {}\n<b>Sink object: </b> {}".format(
            description, sinkFilename, sinkLineNumber, sinkObject
        )
        return description, pathnode

    # Process one result = one pathId for scanner "Checkmarx Scan detailed"
    # Create the finding and add it into the dupes list
    def process_result_detailed(self, dupes, findingdetail, query, result, find_date):
        name, cwe, categories = self.getQueryElements(query)
        title = ""
        sev = result.get("Severity")
        title = query.get("name").replace("_", " ")
        # Loop over <Path> (there should be only one)
        paths = result.findall("Path")
        if (len(paths)) > 1:
            logger.warning(
                "Checkmarx scan: more than one path found: "
                + str(len(paths))
                + ". Only the last one will be used"
            )

        for path in paths:
            sourceFilename = ""
            sinkFilename = ""
            sourceLineNumber = None
            sinkLineNumber = None
            sourceObject = ""
            sinkObject = ""
            similarityId = str(path.get("SimilarityId"))
            path_id = str(path.get("PathId"))
            pathId = similarityId + path_id
            findingdetail = "{}-----\n".format(findingdetail)
            # Loop over function calls / assignments in the data flow graph
            for pathnode in path.findall("PathNode"):
                findingdetail = self.get_description_detailed(pathnode, findingdetail)
                nodeId = pathnode.find("NodeId").text
                if nodeId == "1":
                    (
                        sourceFilename,
                        sourceLineNumber,
                        sourceObject,
                    ) = self.get_pathnode_elements(pathnode)
            # the last pathnode is the sink
            sinkFilename, sinkLineNumber, sinkObject = self.get_pathnode_elements(
                pathnode
            )
            # pathId is the unique id from tool which means that there is basically no aggregation except real duplicates
            aggregateKeys = "{}{}{}{}{}".format(
                categories, cwe, name, sinkFilename, pathId
            )
            if title and sinkFilename:
                title = "{} ({})".format(title, ntpath.basename(sinkFilename))

            find = Finding(
                title=title,
                cwe=int(cwe),
                test=self.test,
                active=False,
                verified=False,
                false_p=result.get("FalsePositive") == "True",
                description=findingdetail,
                severity=sev,
                numerical_severity=Finding.get_numerical_severity(sev),
                mitigation=self.mitigation,
                impact=self.impact,
                references=self.references,
                file_path=sinkFilename,
                line=sinkLineNumber,
                url="N/A",
                date=find_date,
                static_finding=True,
                unique_id_from_tool=pathId,
                sast_source_object=sourceObject,
                sast_sink_object=sinkObject,
                sast_source_line=sourceLineNumber,
                sast_source_file_path=sourceFilename,
            )
        dupes[aggregateKeys] = find

    # Return filename, lineNumber and object (function/parameter...) for a given pathnode
    def get_pathnode_elements(self, pathnode):
        return (
            pathnode.find("FileName").text,
            pathnode.find("Line").text,
            pathnode.find("Name").text,
        )

    # Builds the finding description for scanner "Checkmarx Scan detailed"
    def get_description_detailed(self, pathnode, findingdetail):
        if pathnode.find("Line").text is not None:
            findingdetail = "{}**Line Number:** {}\n".format(
                findingdetail, pathnode.find("Line").text
            )

        if pathnode.find("Column").text is not None:
            findingdetail = "{}**Column:** {}\n".format(
                findingdetail, pathnode.find("Column").text
            )

        if pathnode.find("Name").text is not None:
            findingdetail = "{}**Source Object:** {}\n".format(
                findingdetail, pathnode.find("Name").text
            )

        for codefragment in pathnode.findall("Snippet/Line"):
            findingdetail = "{}**Number:** {}\n**Code:** {}\n".format(
                findingdetail,
                codefragment.find("Number").text,
                codefragment.find("Code").text.strip(),
            )

        findingdetail = "{}-----\n".format(findingdetail)
        return findingdetail

    # Get name, cwe and categories from the global query tag (1 query = 1 type of vulnerability)
    def getQueryElements(self, query):
        categories = ""
        name = query.get("name")
        cwe = query.get("cweId")
        if query.get("categories") is not None:
            categories = query.get("categories")
        return name, cwe, categories
