import json

from dojo.models import Finding


class PhpSymfonySecurityCheckParser(object):
    def get_findings(self, json_file, test):
        tree = self.parse_json(json_file)
        return self.get_items(tree, test)

    def parse_json(self, json_file):
        if json_file is None:
            self.items = []
            return
        try:
            data = json_file.read()
            try:
                tree = json.loads(str(data, "utf-8"))
            except:
                tree = json.loads(data)
        except:
            raise Exception("Invalid format")

        return tree

    def get_items(self, tree, test):
        # print(('tree: ', tree))
        items = {}

        for dependency_name, dependency_data in list(tree.items()):
            advisories = dependency_data.get("advisories")
            dependency_version = dependency_data["version"]
            if dependency_version and dependency_version.startswith("v"):
                dependency_version = dependency_version[1:]

            for advisory in advisories:
                item = get_item(dependency_name, dependency_version, advisory, test)
                unique_key = str(dependency_name) + str(
                    dependency_data["version"] + str(advisory["cve"])
                )
                items[unique_key] = item
                # print(('item: ', item))

        return list(items.values())


def get_item(dependency_name, dependency_version, advisory, test):

    finding = Finding(
        title=dependency_name
        + " - "
        + "("
        + dependency_version
        + ", "
        + advisory["cve"]
        + ")",
        test=test,
        # TODO decide how to handle the fact we don't have a severity. None will lead to problems handling minimum severity on import
        severity="Info",
        description=advisory["title"],
        # TODO Decide if the default '1035: vulnerable 3rd party component' is OK to use?
        cwe=1035,
        cve=advisory["cve"],
        mitigation="upgrade",
        references=advisory["link"],
        active=False,
        verified=False,
        false_p=False,
        duplicate=False,
        out_of_scope=False,
        mitigated=None,
        impact="No impact provided",
        static_finding=True,
        dynamic_finding=False,
        component_name=dependency_name,
        component_version=dependency_version,
    )

    return finding
