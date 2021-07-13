from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

import unittest
import sys
import os
from base_test_class import BaseTestCase, on_exception_html_source_logger, set_suite_settings
from product_test import ProductTest, WaitForPageLoad

dir_path = os.path.dirname(os.path.realpath(__file__))


class FindingTest(BaseTestCase):

    def test_list_findings_all(self):
        return self.test_list_findings('finding/all')

    def test_list_findings_closed(self):
        return self.test_list_findings('finding/closed')

    def test_list_findings_accepted(self):
        return self.test_list_findings('finding/accepted')

    def test_list_findings_open(self):
        return self.test_list_findings('finding/open')

    def test_list_findings(self, suffix):
        # bulk edit dropdown menu
        driver = self.driver
        driver.get(self.base_url + "finding")

        driver.find_element_by_id("select_all").click()

        driver.find_element_by_id("dropdownMenu2").click()

        bulk_edit_menu = driver.find_element_by_id("bulk_edit_menu")
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_active").is_enabled(), False)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_verified").is_enabled(), False)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_false_p").is_enabled(), False)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_out_of_scope").is_enabled(), False)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_is_mitigated").is_enabled(), False)

        driver.find_element_by_id("id_bulk_status").click()

        bulk_edit_menu = driver.find_element_by_id("bulk_edit_menu")
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_active").is_enabled(), True)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_verified").is_enabled(), True)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_false_p").is_enabled(), True)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_out_of_scope").is_enabled(), True)
        self.assertEqual(bulk_edit_menu.find_element_by_id("id_bulk_is_mitigated").is_enabled(), True)

    @on_exception_html_source_logger
    def test_edit_finding(self):
        # The Name of the Finding created by test_add_product_finding => 'App Vulnerable to XSS'
        # Test To Add Finding To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Edit Finding`
        driver.find_element_by_link_text("Edit Finding").click()
        # Change: 'Severity' and 'cvssv3'
        # finding Severity
        Select(driver.find_element_by_id("id_severity")).select_by_visible_text("Critical")
        # cvssv3
        driver.find_element_by_id("id_cvssv3").send_keys("CVSS:3.0/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H")
        # "Click" the Done button to Edit the finding
        driver.find_element_by_xpath("//input[@name='_Finished']").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding saved successfully'))

    def test_add_image(self):
        # print("\n\nDebug Print Log: testing 'add image' \n")
        # The Name of the Finding created by test_add_product_finding => 'App Vulnerable to XSS'
        # Test To Add Finding To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Edit Finding`
        driver.find_element_by_link_text("Manage Files").click()
        # select first file input field: form-0-image
        # Set full image path for image file 'strange.png
        image_path = os.path.join(dir_path, 'finding_image.png')
        driver.find_element_by_id("id_form-0-file").send_keys(image_path)
        driver.find_element_by_id("id_form-0-title").send_keys('Image Title')
        # Save uploaded image
        with WaitForPageLoad(driver, timeout=50):
            driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Files updated successfully.'))

    def test_mark_finding_for_review(self):
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Request Peer Reveiw`
        driver.find_element_by_link_text("Request Peer Review").click()
        # select Reviewer
        # Let's make the first user in the list a reviewer
        # set select element style from 'none' to 'inline'

        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'id_reviewers_chosen')))
        except TimeoutException:
            self.fail('Timed out waiting for reviewer dropdown to initialize ')

        driver.execute_script("document.getElementsByName('reviewers')[0].style.display = 'inline'")
        # select the first option tag
        element = driver.find_element_by_xpath("//select[@name='reviewers']")
        reviewer_option = element.find_elements_by_tag_name('option')[0]
        Select(element).select_by_value(reviewer_option.get_attribute("value"))
        # Add Review notes
        driver.find_element_by_id("id_entry").clear()
        driver.find_element_by_id("id_entry").send_keys("This is to be reveiwed critically. Make sure it is well handled.")
        # Click 'Mark for reveiw'
        driver.find_element_by_name("submit").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding marked for review and reviewers notified.'))

    @on_exception_html_source_logger
    def test_clear_review_from_finding(self):
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on `Clear Review` link text
        driver.find_element_by_link_text("Clear Review").click()
        # Mark Active and Verified checkboxes
        driver.find_element_by_id('id_active').click()
        driver.find_element_by_id('id_verified').click()
        # Add Review notes
        driver.find_element_by_id("id_entry").clear()
        driver.find_element_by_id("id_entry").send_keys("This has been reviewed and confirmed. A fix needed here.")
        # Click 'Clear reveiw' button
        driver.find_element_by_name("submit").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding review has been updated successfully.'))

    def test_delete_image(self):
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Edit Finding`
        driver.find_element_by_link_text("Manage Files").click()
        # mark delete checkbox for first file input field: form-0-DELETE
        driver.find_element_by_id("id_form-0-DELETE").click()
        # Save selection(s) for image deletion
        driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Files updated successfully.'))

    def test_close_finding(self):
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Get the status of the current endpoint
        pre_status = driver.find_element_by_xpath('//*[@id="vuln_endpoints"]/tbody/tr/td[3]').text
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Close Finding`
        driver.find_element_by_link_text("Close Finding").click()
        # fill notes stating why finding should be closed
        driver.find_element_by_id("id_entry").send_keys("All issues in this Finding have been resolved successfully")
        # click 'close Finding' submission button
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the finding has been added
        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding closed.'))
        # Check to see if the endpoint was mitigated
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Get the status of the current endpoint
        # This will throw exception if the test fails due to invalid xpath
        post_status = driver.find_element_by_xpath('//*[@id="remd_endpoints"]/tbody/tr/td[3]').text
        # Assert ot the query to dtermine status of failure
        self.assertTrue(pre_status != post_status)

    def test_open_finding(self):
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Get the status of the current endpoint
        pre_status = driver.find_element_by_xpath('//*[@id="remd_endpoints"]/tbody/tr/td[3]').text
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Open Finding`
        driver.find_element_by_link_text("Open Finding").click()
        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding Reopened.'))
        # Check to see if the endpoint was set to active again
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Get the status of the current endpoint
        # This will throw exception if the test fails due to invalid xpath
        post_status = driver.find_element_by_xpath('//*[@id="vuln_endpoints"]/tbody/tr/td[3]').text
        # Assert ot the query to dtermine status of failure
        self.assertTrue(pre_status != post_status)

    def test_make_finding_a_template(self):
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Make Finding a Template`
        driver.find_element_by_link_text("Make Finding a Template").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding template added successfully. You may edit it here.'))

    def test_apply_template_to_a_finding(self):
        driver = self.driver
        # Navigate to All Finding page
        print("\nListing findings \n")
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        # print("\nClicking on dropdown menu \n")
        driver.find_element_by_id("dropdownMenu1").click()
        self.assertNoConsoleErrors()

        # Click on `Apply Template to Finding`
        # print("\nClicking on apply template \n")
        driver.find_element_by_link_text("Apply Template to Finding").click()
        self.assertNoConsoleErrors()
        # click on the template of 'App Vulnerable to XSS'
        print("\nClicking on the template \n")
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        self.assertNoConsoleErrors()
        # Click on 'Replace all' button
        print("\nClicking on replace all \n")
        driver.find_element_by_xpath("//button[@data-option='Replace']").click()
        self.assertNoConsoleErrors()
        # Click the 'finished' button to submit
        # print("\nClicking on finished \n")
        driver.find_element_by_name('_Finished').click()
        self.assertNoConsoleErrors()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_text_present_on_page(text='App Vulnerable to XSS'))

    @on_exception_html_source_logger
    def test_delete_finding_template(self):
        driver = self.driver
        # Navigate to All Finding page
        driver.get(self.base_url + "template")
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on `Delete Template` button
        driver.find_element_by_xpath("//button[text()='Delete Template']").click()
        # Click 'Yes' on Alert popup
        driver.switch_to.alert.accept()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding Template deleted successfully.'))

    def test_import_scan_result(self):
        driver = self.driver
        # Navigate to All Finding page
        self.goto_all_findings_list(driver)
        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'Finding' dropdown menubar
        driver.find_element_by_partial_link_text("Findings").click()
        # Click on `Import Scan Results` link text
        driver.find_element_by_link_text("Import Scan Results").click()
        # Select `ZAP Scan` as Scan Type
        Select(driver.find_element_by_id("id_scan_type")).select_by_visible_text('ZAP Scan')
        # Select `Default` as the Environment
        Select(driver.find_element_by_id("id_environment")).select_by_visible_text('Development')
        # upload scan file
        file_path = os.path.join(dir_path, 'zap_sample.xml')
        driver.find_element_by_name("file").send_keys(file_path)
        # Click Submit button
        with WaitForPageLoad(driver, timeout=50):
            driver.find_elements_by_css_selector("button.btn.btn-primary")[1].click()
        # Query the site to determine if the finding has been added
        # print("\n\nDebug Print Log: findingTxt fetched: {}\n".format(productTxt))
        # print("Checking for '.*ZAP Scan processed a total of 4 findings.*'")
        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='ZAP Scan processed a total of 4 findings'))

    def test_delete_finding(self):
        # The Name of the Finding created by test_add_product_finding => 'App Vulnerable to XSS'
        # Test To Add Finding To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to All Finding page
        # driver.get(self.base_url + "finding")
        self.goto_all_findings_list(driver)

        # Select and click on the particular finding to edit
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        # Click on the 'dropdownMenu1 button'
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on `Delete Finding`
        driver.find_element_by_link_text("Delete Finding").click()
        # Click 'Yes' on Alert popup
        driver.switch_to.alert.accept()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text='Finding deleted successfully'))
        # check that user was redirect back to url where it came from based on return_url

    def test_list_components(self):
        driver = self.driver
        self.goto_component_overview(driver)
        self.assertTrue(self.is_element_by_css_selector_present("table"))


def add_finding_tests_to_suite(suite, jira=False, github=False, block_execution=False):
    suite.addTest(BaseTestCase('test_login'))
    set_suite_settings(suite, jira=jira, github=github, block_execution=block_execution)

    # Add each test the the suite to be run
    # success and failure is output by the test
    suite.addTest(ProductTest('test_create_product'))
    suite.addTest(ProductTest('test_add_product_finding'))
    # TODO add some more findings with different statuses
    suite.addTest(FindingTest('test_list_findings_all'))
    suite.addTest(FindingTest('test_list_findings_closed'))
    suite.addTest(FindingTest('test_list_findings_accepted'))
    suite.addTest(FindingTest('test_list_findings_open'))
    suite.addTest(FindingTest('test_list_components'))
    suite.addTest(FindingTest('test_edit_finding'))
    suite.addTest(FindingTest('test_add_image'))
    suite.addTest(FindingTest('test_delete_image'))
    suite.addTest(FindingTest('test_mark_finding_for_review'))
    suite.addTest(FindingTest('test_clear_review_from_finding'))
    suite.addTest(FindingTest('test_close_finding'))
    suite.addTest(FindingTest('test_open_finding'))
    suite.addTest(FindingTest('test_make_finding_a_template'))
    suite.addTest(FindingTest('test_apply_template_to_a_finding'))
    suite.addTest(FindingTest('test_import_scan_result'))
    suite.addTest(FindingTest('test_delete_finding'))
    suite.addTest(FindingTest('test_delete_finding_template'))
    suite.addTest(ProductTest('test_delete_product'))
    return suite


def suite():
    suite = unittest.TestSuite()
    add_finding_tests_to_suite(suite, jira=False, github=False, block_execution=False)
    add_finding_tests_to_suite(suite, jira=True, github=True, block_execution=True)
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
