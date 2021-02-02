import json

from dojo.models import Finding


class ChoctawhogParser(object):
    def get_findings(self, json_output, test):
        if json_output is None:
            return list()

        tree = self.parse_json(json_output)
        if tree:
            return [data for data in self.get_items(tree, test)]
        else:
            return list()

    def parse_json(self, json_output):
        try:
            data = json_output.read()
            try:
                tree = json.loads(str(data, "utf-8"))
            except:
                tree = json.loads(data)
        except:
            raise Exception("Invalid format")

        return tree

    def get_items(self, tree, test):
        items = {}
        for node in tree:
            item = get_item(node, test)
            unique_key = "Finding {}".format(tree.index(node))
            items[unique_key] = item

        return list(items.values())


def get_item(vulnerability, test):
    cwe = 200
    description = "This string was found: {}".format(vulnerability.get("stringsFound"))
    description += "\nCommit message: {}".format(vulnerability.get("commit"))
    description += "\nCommit hash: {}".format(vulnerability.get("commitHash"))
    description += "\nParent commit hash: {}".format(
        vulnerability.get("parent_commit_hash")
    )
    description += "\nDate: {}".format(vulnerability.get("date"))
    description += "\nOld and new file IDs: {} - {}".format(
        vulnerability.get("old_file_id"), vulnerability.get("new_file_id")
    )
    description += "\nOld and new line numbers: {} - {}".format(
        vulnerability.get("old_line_num"), vulnerability.get("new_line_num")
    )
    file_path = vulnerability.get("path")
    title = "{} found in {} ({})".format(
        vulnerability.get("reason"),
        vulnerability.get("path"),
        vulnerability.get("commitHash"),
    )

    # create the finding object
    finding = Finding(
        title=title,
        test=test,
        severity="High",
        cwe=cwe,
        description=description,
        mitigation="Please ensure no secret material nor confidential information is kept in clear within git repositories.",
        file_path=file_path,
        static_finding=True,
        dynamic_finding=False,
    )

    finding.description = finding.description.strip()

    return finding
