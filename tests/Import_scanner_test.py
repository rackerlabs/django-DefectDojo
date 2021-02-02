from selenium.webdriver.support.ui import Select
import unittest
import re
import sys
import os
import git
import shutil
from base_test_class import BaseTestCase
from product_test import ProductTest


class ScannerTest(BaseTestCase):
    def setUp(self):
        super().setUp(self)
        self.repo_path = dir_path + "/scans"
        if os.path.isdir(self.repo_path):
            shutil.rmtree(self.repo_path)
        os.mkdir(self.repo_path)
        scan_types = git.Repo.clone_from(
            "https://github.com/DefectDojo/sample-scan-files", self.repo_path
        )
        self.remove_items = [
            "__init__.py",
            "__init__.pyc",
            "factory.py",
            "factory.pyc",
            "factory.py",
            "LICENSE",
            "README.md",
            ".gitignore",
            ".git",
            "__pycache__",
        ]
        tool_path = dir_path[:-5] + "dojo/tools"
        tools = sorted(os.listdir(tool_path))
        tests = sorted(os.listdir(self.repo_path))
        self.tools = [i for i in tools if i not in self.remove_items]
        self.tests = [i for i in tests if i not in self.remove_items]

    def test_check_test_file(self):
        missing_tests = ["MISSING TEST FOLDER"]
        for tool in self.tools:
            if tool not in self.tests:
                missing_tests += [tool]

        missing_tests += ["\nNO TEST FILES"]

        for test in self.tests:
            cases = sorted(os.listdir(self.repo_path + "/" + test))
            cases = [i for i in cases if i not in self.remove_items]
            if len(cases) == 0 and tool not in missing_tests:
                missing_tests += [test]

        if len(missing_tests) > 0:
            print("The following scanners are missing test cases or incorrectly named")
            print("Names must match those listed in /dojo/tools")
            print("Test cases can be added/modified here:")
            print("https://github.com/DefectDojo/sample-scan-files\n")
            for test in missing_tests:
                print(test)
            print()
        assert len(missing_tests) == 0

    def test_check_for_doc(self):
        driver = self.driver
        driver.get("https://defectdojo.readthedocs.io/en/latest/integrations.html")

        integration_index = (
            integration_text.index("Integrations") + len("Integrations") + 1
        )
        usage_index = integration_text.index("Usage Examples") - len("Models") - 2
        integration_text = integration_text[integration_index:usage_index].lower()
        integration_text = (
            integration_text.replace("_", " ")
            .replace("-", " ")
            .replace(".", "")
            .split("\n")
        )
        acronyms = []
        for words in integration_text:
            acronyms += ["".join(word[0] for word in words.split())]

        missing_docs = []
        for tool in self.tools:
            reg = re.compile(".*" + tool.replace("_", " ") + ".*")
            if len(list(filter(reg.search, integration_text))) < 1:
                if len(list(filter(reg.search, acronyms))) < 1:
                    missing_docs += [tool]

        if len(missing_docs) > 0:
            print("The following scanners are missing documentation")
            print("Names must match those listed in /dojo/tools")
            print("Documentation can be added here:")
            print("https://github.com/DefectDojo/Documentation\n")
            for tool in missing_docs:
                print(tool)
            print()
        assert len(missing_docs) == 0

    def test_check_for_fixtures(self):
        fixture_path = dir_path[:-5] + "dojo/fixtures/test_type.json"
        file = open(fixture_path, "r+")
        fixtures = file.readlines()
        file.close()

        fixtures = [
            fix.replace("\t", "")
            .replace("\n", "")
            .replace(".", "")
            .replace("-", " ")
            .strip()
            .lower()
            for fix in fixtures
        ]
        remove_items = [
            "{",
            "},",
            "}",
            "[",
            "]",
            '"fields": {',
            '"model": "dojotest_type",',
        ]
        fixtures = [fix for fix in fixtures if fix not in remove_items]
        remove_patterns = ['"', "name: ", "pk: ", " scan", " scanner"]
        for pattern in remove_patterns:
            fixtures = [re.sub(pattern, "", fix) for fix in fixtures]
        fixtures = fixtures[fixtures.index("100") - 1 :]
        fixtures = list(filter((re.compile(r"\D")).match, fixtures))

        acronyms = []
        for words in fixtures:
            acronyms += ["".join(word[0] for word in words.split())]

        missing_fixtures = []
        for tool in self.tools:
            reg = re.compile(tool.replace("_", " "))
            matches = list(filter(reg.search, fixtures)) + list(
                filter(reg.search, acronyms)
            )
            matches = [m.strip() for m in matches]
            if len(matches) != 1:
                if tool not in matches:
                    missing_fixtures += [tool]

        if len(missing_fixtures) > 0:
            print("The following scanners are missing fixtures")
            print("Names must match those listed in /dojo/tools")
            print("Fixtures can be added here:")
            print(
                "https://github.com/DefectDojo/django-DefectDojo/blob/master/dojo/fixtures/test_type.json\n"
            )
            for tool in missing_fixtures:
                print(tool)
            print()
        assert len(missing_fixtures) == 0

    def test_check_for_forms(self):
        forms_path = dir_path[:-5] + "dojo/forms.py"
        file = open(forms_path, "r+")
        forms = file.readlines()
        file.close()

        forms = [form.strip().lower() for form in forms]
        forms = forms[
            forms.index('scan_type_choices = (("", "please select a scan type"),')
            + 1 : forms.index(
                "sorted_scan_type_choices = sorted(scan_type_choices, key=lambda x: x[1])"
            )
            - 1
        ]
        forms = [
            form.replace("(", "")
            .replace(")", "")
            .replace("-", " ")
            .replace('"', "")
            .replace(".", "")
            for form in forms
        ]
        forms = [form[: form.index(",")] for form in forms]
        remove_patterns = [" scanner", " scan"]
        for pattern in remove_patterns:
            forms = [re.sub(pattern, "", fix) for fix in sorted(forms)]

        acronyms = []
        for words in forms:
            acronyms += ["".join(word[0] for word in words.split())]

        missing_forms = []
        for tool in self.tools:
            reg = re.compile(tool.replace("_", " "))
            matches = list(filter(reg.search, forms)) + list(
                filter(reg.search, acronyms)
            )
            matches = [m.strip() for m in matches]
            if len(matches) != 1:
                if tool not in matches:
                    missing_forms += [tool]

        if len(missing_forms) > 0:
            print("The following scanners are missing forms")
            print("Names must match those listed in /dojo/tools")
            print("forms can be added here:")
            print(
                "https://github.com/DefectDojo/django-DefectDojo/blob/master/dojo/forms.py\n"
            )
            for tool in missing_forms:
                print(tool)
            print()
        assert len(missing_forms) == 0

    @unittest.skip("Deprecated since Dynamic Parser infrastructure")
    def test_check_for_options(self):
        template_path = dir_path[:-5] + "dojo/templates/dojo/import_scan_results.html"
        file = open(template_path, "r+")
        templates = file.readlines()
        file.close()

        templates = [temp.strip().lower() for temp in templates]
        templates = templates[templates.index("<ul>") + 1 : templates.index("</ul>")]
        remove_patterns = ["<li><b>", "</b>", "</li>", " scanner", " scan"]
        for pattern in remove_patterns:
            templates = [re.sub(pattern, "", temp) for temp in templates]

        templates = [
            temp[: temp.index(" - ")] for temp in sorted(templates) if " - " in temp
        ]
        templates = [
            temp.replace("-", " ").replace(".", "").replace("(", "").replace(")", "")
            for temp in templates
        ]

        acronyms = []
        for words in templates:
            acronyms += ["".join(word[0] for word in words.split())]

        missing_templates = []
        for tool in self.tools:
            temp_tool = tool.replace("_", " ")
            reg = re.compile(temp_tool)
            matches = list(filter(reg.search, templates)) + list(
                filter(reg.search, acronyms)
            )
            matches = [m.strip() for m in matches]
            if len(matches) == 0:
                if temp_tool not in matches:
                    missing_templates += [tool]

        if len(missing_templates) > 0:
            print("The following scanners are missing templates")
            print("Names must match those listed in /dojo/tools")
            print("templates can be added here:")
            print(
                "https://github.com/DefectDojo/django-DefectDojo/blob/master/dojo/templates/dojo/import_scan_results.html\n"
            )
            for tool in missing_templates:
                print(tool)
            print()
        assert len(missing_templates) == 0

    def test_engagement_import_scan_result(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_class_name("pull-left").click()
        driver.find_element_by_link_text("Add New Engagement").click()
        driver.find_element_by_id("id_name").send_keys("Scan type mapping")
        driver.find_element_by_name("_Import Scan Results").click()
        options_text = "".join(driver.find_element_by_name("scan_type").text).split(
            "\n"
        )
        options_text = [scan.strip() for scan in options_text]

        mod_options = options_text
        mod_options = [re.sub(" Scanner", "", scan) for scan in mod_options]
        mod_options = [re.sub(" Scan", "", scan) for scan in mod_options]
        mod_options = [
            scan.lower().replace("-", " ").replace(".", "") for scan in mod_options
        ]

        acronyms = []
        for scans in mod_options:
            acronyms += ["".join(scan[0] for scan in scans.split())]

        potential_matches = mod_options + acronyms
        scan_map = {}

        for test in self.tests:
            temp_test = test.replace("_", " ").replace("-", " ")
            reg = re.compile(".*" + temp_test + ".*")
            found_matches = {}
            for i in range(len(potential_matches)):
                matches = list(filter(reg.search, [potential_matches[i]]))
                if len(matches) > 0:
                    index = i
                    if i >= len(mod_options):
                        index = i - len(mod_options)
                    found_matches[index] = matches[0]

            if len(found_matches) == 1:
                index = list(found_matches.keys())[0]
                scan_map[test] = options_text[index]
            elif len(found_matches) > 1:
                try:
                    index = list(found_matches.values()).index(temp_test)
                    scan_map[test] = options_text[list(found_matches.keys())[index]]
                except:
                    pass

        failed_tests = []
        for test in self.tests:
            cases = sorted(os.listdir(self.repo_path + "/" + test))
            cases = [i for i in cases if i not in self.remove_items]
            if len(cases) == 0:
                failed_tests += [test.upper() + ": No test cases"]
            for case in cases:
                self.goto_product_overview(driver)
                driver.find_element_by_class_name("pull-left").click()
                driver.find_element_by_link_text("Add New Engagement").click()
                driver.find_element_by_id("id_name").send_keys(test + " - " + case)
                driver.find_element_by_name("_Import Scan Results").click()
                try:
                    driver.find_element_by_id("id_active").get_attribute("checked")
                    driver.find_element_by_id("id_verified").get_attribute("checked")
                    scan_type = scan_map[test]
                    Select(
                        driver.find_element_by_id("id_scan_type")
                    ).select_by_visible_text(scan_type)
                    test_location = self.repo_path + "/" + test + "/" + case
                    driver.find_element_by_id("id_file").send_keys(test_location)
                    driver.find_element_by_css_selector("input.btn.btn-primary").click()
                    EngagementTXT = "".join(
                        driver.find_element_by_tag_name("BODY").text
                    ).split("\n")
                    reg = re.compile("processed, a total of")
                    matches = list(filter(reg.search, EngagementTXT))
                    if len(matches) != 1:
                        failed_tests += [test.upper() + " - " + case + ": Not imported"]
                except Exception as e:
                    if e == "Message: timeout":
                        failed_tests += [
                            test.upper()
                            + " - "
                            + case
                            + ": Not imported due to timeout"
                        ]
                    else:
                        failed_tests += [
                            test.upper() + ": Cannot auto select scan type"
                        ]
                    break

        if len(failed_tests) > 0:
            print("The following scan imports produced errors")
            print("Names of tests must match those listed in /dojo/tools")
            print("Tests can be added/modified here:")
            print("https://github.com/DefectDojo/sample-scan-files\n")
            for test in failed_tests:
                print(test)
            print()
        assert len(failed_tests) == 0

    def tearDown(self):
        super().tearDown(self)
        shutil.rmtree(self.repo_path)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(ScannerTest("test_check_test_file"))
    suite.addTest(ScannerTest("test_check_for_doc"))
    suite.addTest(ScannerTest("test_check_for_fixtures"))
    suite.addTest(ScannerTest("test_check_for_forms"))
    suite.addTest(ScannerTest("test_check_for_options"))
    suite.addTest(ProductTest("test_create_product"))
    suite.addTest(ScannerTest("test_engagement_import_scan_result"))
    suite.addTest(ProductTest("test_delete_product"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
