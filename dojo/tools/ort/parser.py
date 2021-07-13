import hashlib
import json
from collections import namedtuple

from dojo.models import Finding


class OrtParser(object):
    """Oss Review Toolkit Parser"""

    def get_scan_types(self):
        return ["ORT evaluated model Importer"]

    def get_label_for_scan_types(self, scan_type):
        return "ORT evaluated model Importer"

    def get_description_for_scan_types(self, scan_type):
        return "Import Outpost24 endpoint vulnerability scan in XML format."

    def get_findings(self, json_output, test):

        if json_output is None:
            return list()

        evaluated_model = self.parse_json(json_output)
        if evaluated_model:
            return self.get_items(evaluated_model, test)
        else:
            return list()

    def parse_json(self, json_output):
        try:
            data = json_output.read()
            try:
                tree = json.loads(str(data, 'utf-8'))
            except:
                tree = json.loads(data)
        except:
            raise Exception("Invalid format")

        return tree

    def get_items(self, evaluatedModel, test):
        items = {}
        packages = evaluatedModel['packages']
        dependency_trees = evaluatedModel['dependency_trees']
        rule_violations = evaluatedModel['rule_violations']
        licenses = evaluatedModel['licenses']
        rule_violations_unresolved = get_unresolved_rule_violations(rule_violations)
        rule_violations_models = get_rule_violation_models(rule_violations_unresolved, packages, licenses,
                                                           dependency_trees)

        for model in rule_violations_models:
            item = get_item(model, test)
            unique_key = hashlib.md5((item.title + item.references).encode()).hexdigest()
            items[unique_key] = item

        return list(items.values())


def get_unresolved_rule_violations(rule_violations):
    rule_violations_unresolved = []
    for violation in rule_violations:
        if is_rule_violation_unresolved(violation):
            rule_violations_unresolved.append(violation)
    return rule_violations_unresolved


def is_rule_violation_unresolved(rule_violation):
    return 'resolutions' not in rule_violation


def find_in_dependency_tree(tree, package_id):
    if 'pkg' in tree and tree['pkg'] == package_id:
        return True
    else:
        if 'children' in tree:
            found_in_child = False
            for child in tree['children']:
                if found_in_child:
                    break
                else:
                    found_in_child = find_in_dependency_tree(child, package_id)
            return found_in_child
        else:
            return False


def get_project_ids_for_package(dependency_trees, package_id):
    project_ids = []
    for project in dependency_trees:
        if find_in_dependency_tree(project, package_id):
            project_ids.append(project['pkg'])
    return project_ids


def get_name_id_for_package(packages, package__id):
    name = ""
    for package in packages:
        if package['_id'] == package__id:
            name = package['id']
            break
    return name


def get_rule_violation_models(rule_violations_unresolved, packages, licenses, dependency_trees):
    models = []
    for violation in rule_violations_unresolved:
        models.append(get_rule_violation_model(violation, packages, licenses, dependency_trees))
    return models


def get_rule_violation_model(rule_violation_unresolved, packages, licenses, dependency_trees):
    project_ids = get_project_ids_for_package(dependency_trees, rule_violation_unresolved['pkg'])
    project_names = []
    for id in project_ids:
        project_names.append(get_name_id_for_package(packages, id))
    package = find_package_by_id(packages, rule_violation_unresolved['pkg'])
    if 'license' in rule_violation_unresolved:
        license_tmp = rule_violation_unresolved['license']
    else:
        license_tmp = 'unset'
    if 'license_source' not in rule_violation_unresolved:
        rule_violation_unresolved['license_source'] = 'unset'
    license_id = find_license_id(licenses, license_tmp)

    return RuleViolationModel(package, license_id, license_tmp, project_names, rule_violation_unresolved)


def find_package_by_id(packages, pkg_id):
    package = None
    for pkg in packages:
        if pkg['_id'] == pkg_id:
            package = pkg
            break
    return package


def find_license_id(licenses, license_id):
    id = ''
    for lic in licenses:
        if lic['_id'] == license_id:
            id = lic['id']
            break
    return id


def find_finding_path(findings, license_num):
    for f in findings:
        if f['type'] == 'LICENSE':
            if license_num == f['license']:
                return f['path']


def get_item(model, test):

    if 'findings' in model.pkg:
        finding_path = find_finding_path(model.pkg['findings'], model.license_id_number)
        desc = f"""root projects: {', '.join(model.projects)}
        source  : {model.rule_violation['license_source']}
        license : {model.license_id}
        package : {model.pkg['id']}
        message : {model.rule_violation['message']}
        path	: {finding_path}
        how to fix : {model.rule_violation['how_to_fix']}"""
    else:
        desc = f"""root projects: {', '.join(model.projects)}
        source  : {model.rule_violation['license_source']}
        license : {model.license_id}
        package : {model.pkg['id']}
        message : {model.rule_violation['message']}
        how to fix : {model.rule_violation['how_to_fix']}"""

    severity = get_severity(model.rule_violation)

    finding = Finding(title=model.rule_violation['rule'],
                      test=test,
                      references=model.rule_violation['message'],
                      description=desc,
                      severity=severity,
                      static_finding=True)

    return finding


# TODO with python 3.7
# @dataclass
# class RuleViolationModel:
#     pkg: dict
#     license_id: str
#     projects: []
#     rule_violation: dict

RuleViolationModel = namedtuple('RuleViolationModel', [
    'pkg',
    'license_id',
    'license_id_number',
    'projects',
    'rule_violation'
])


def get_severity(rule_violation):
    if rule_violation['severity'] == 'ERROR':
        return 'High'
    elif rule_violation['severity'] == 'WARNING':
        return 'Medium'
    elif rule_violation['severity'] == 'HINT':
        return 'Info'
    else:
        return 'Critical'
