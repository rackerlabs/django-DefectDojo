from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unittest
import sys
import os
from base_test_class import BaseTestCase
from product_test import ProductTest

dir_path = os.path.dirname(os.path.realpath(__file__))


class ReportBuilderTest(BaseTestCase):

    # Move the report blocks from Available Widgets to Report Format
    def move_blocks(self, driver):
        in_use = driver.find_element_by_id("sortable2")
        available_widgets = driver.find_element_by_id("sortable1").find_elements_by_tag_name("li")
        for widget in available_widgets:
            ActionChains(driver).drag_and_drop(widget, in_use).perform()

    # Fill in the boxes
    def enter_values(self, driver):
        in_use = driver.find_element_by_id("sortable2").find_elements_by_tag_name("li")
        for widget in in_use:
            class_names = widget.get_attribute("class")
            if 'cover-page' in class_names:
                inputs = widget.find_elements_by_tag_name("input")
                for field in inputs:
                    field.send_keys('cover words')
            if 'wysiwyg-content' in class_names:
                content = widget.find_element_by_class_name("editor").send_keys('wysiwyg')

    def generate_HTML_report(self):
        driver = self.driver
        driver.get(self.base_url + "reports/builder")
        self.move_blocks(driver)
        self.enter_values(driver)
        Select(driver.find_element_by_id("id_report_type")).select_by_visible_text("HTML")
        driver.find_element_by_id("id_report_name").send_keys('Test Report')
        driver.find_element_by_class_name("run_report").click()
        self.assertTrue(driver.current_url == self.base_url + "reports/custom")

    def generate_AsciiDoc_report(self):
        driver = self.driver
        driver.get(self.base_url + "reports/builder")
        self.move_blocks(driver)
        self.enter_values(driver)
        Select(driver.find_element_by_id("id_report_type")).select_by_visible_text("AsciiDoc")
        driver.find_element_by_id("id_report_name").send_keys('Test Report')
        driver.find_element_by_class_name("run_report").click()
        self.assertTrue(driver.current_url == self.base_url + "reports/custom")

    def test_product_type_report(self):
        driver = self.driver
        driver.get(self.base_url + "product/type")
        driver.find_element_by_id("dropdownMenuProductType").click()
        driver.find_element_by_partial_link_text('Report').click()
        my_select = Select(driver.find_element_by_id("id_include_finding_notes"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_table_of_contents"))
        my_select.select_by_index(1)

        driver.find_element_by_name('_generate').click()

    def test_product_report(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_link_text("QA Test").click()
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_partial_link_text('Product Report').click()

        my_select = Select(driver.find_element_by_id("id_include_finding_notes"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_table_of_contents"))
        my_select.select_by_index(1)

        driver.find_element_by_name('_generate').click()

    def test_engagement_report(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_link_text("QA Test").click()
        driver.find_element_by_partial_link_text('Engagements').click()
        driver.find_element_by_link_text("View Engagements").click()
        driver.find_element_by_link_text("Ad Hoc Engagement").click()
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_partial_link_text('Report').click()
        my_select = Select(driver.find_element_by_id("id_include_finding_notes"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_table_of_contents"))
        my_select.select_by_index(1)

        driver.find_element_by_name('_generate').click()

    def test_test_report(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_link_text("QA Test").click()
        driver.find_element_by_partial_link_text('Engagements').click()
        driver.find_element_by_link_text("View Engagements").click()
        driver.find_element_by_link_text("Ad Hoc Engagement").click()
        driver.find_element_by_link_text("Pen Test").click()
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_partial_link_text('Report').click()
        my_select = Select(driver.find_element_by_id("id_include_finding_notes"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_table_of_contents"))
        my_select.select_by_index(1)

        driver.find_element_by_name('_generate').click()

    def test_product_endpoint_report(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_link_text("QA Test").click()
        driver.find_element_by_partial_link_text('Endpoints').click()
        driver.find_element_by_link_text("Endpoint Report").click()

        # extra dropdown click
        # print('waiting for show-filters to appear due to the amazing javascript we have...')
        dropdown = WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, "show-filters")))

        dropdown = driver.find_element_by_id("show-filters")
        dropdown.click()

        # print('waiting for filter section to expand...')
        my_select = WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.XPATH, "//label[@for='id_include_finding_notes']")))

        my_select = Select(driver.find_element_by_id("id_include_finding_notes"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_table_of_contents"))
        my_select.select_by_index(1)

        driver.find_element_by_name('_generate').click()

    def test_product_list_report(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_link_text("Findings Report").click()

        my_select = Select(driver.find_element_by_id("id_include_finding_notes"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_executive_summary"))
        my_select.select_by_index(1)

        my_select = Select(driver.find_element_by_id("id_include_table_of_contents"))
        my_select.select_by_index(1)

        driver.find_element_by_name('_generate').click()


def add_report_tests_to_suite(suite):
    # Add each test the the suite to be run
    # success and failure is output by the test
    suite.addTest(BaseTestCase('test_login'))
    suite.addTest(BaseTestCase('disable_block_execution'))
    suite.addTest(ProductTest('test_create_product'))
    suite.addTest(ProductTest('test_add_product_finding'))
    suite.addTest(ProductTest('test_add_product_endpoints'))

    suite.addTest(ReportBuilderTest('generate_HTML_report'))
    suite.addTest(ReportBuilderTest('generate_AsciiDoc_report'))

    # we add reports here as we now have a product that triggers some logic inside reports
    suite.addTest(ReportBuilderTest('test_product_type_report'))
    suite.addTest(ReportBuilderTest('test_product_report'))
    suite.addTest(ReportBuilderTest('test_engagement_report'))
    suite.addTest(ReportBuilderTest('test_test_report'))
    suite.addTest(ReportBuilderTest('test_product_endpoint_report'))

    suite.addTest(ProductTest('test_delete_product'))
    return suite


def suite():
    suite = unittest.TestSuite()
    add_report_tests_to_suite(suite)
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
