import unittest
import sys
import os
import time
from base_test_class import BaseTestCase
from product_test import ProductTest, WaitForPageLoad

dir_path = os.path.dirname(os.path.realpath(__file__))


class FileUploadTest(BaseTestCase):
    def uncollapse_all(self, driver):
        elems = driver.find_elements_by_name("collapsible")
        for elem in elems:
            elem.click()
            time.sleep(0.5)
        return driver

    def test_add_file_finding_level(self):
        # print("\n\nDebug Print Log: testing 'add image' \n")
        # The Name of the Finding created by test_add_product_finding => 'App Vulnerable to XSS'
        # Test To Add Finding To product
        # login to site, password set to fetch from environ
        driver = self.login_page()
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
        image_path = os.path.join(dir_path, "finding_image.png")
        driver.find_element_by_id("id_form-0-title").send_keys("Finding Title")
        driver.find_element_by_id("id_form-0-file").send_keys(image_path)
        # Save uploaded image
        with WaitForPageLoad(driver, timeout=50):
            driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added
        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Files updated successfully")
        )

    def test_delete_file_finding_level(self):
        # login to site, password set to fetch from environ
        driver = self.login_page()
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
        self.assertTrue(
            self.is_success_message_present(text="Files updated successfully")
        )

    def test_add_file_test_level(self):
        # View existing test from ProductTest()
        # Login to the site.
        driver = self.login_page()
        # goto engagemnent list (and wait for javascript to load)
        self.goto_all_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()
        driver.find_element_by_partial_link_text("Pen Test").click()
        driver.find_element_by_name("Manage Files").click()
        # select first file input field: form-0-image
        # Set full image path for image file 'strange.png
        image_path = os.path.join(dir_path, "finding_image.png")
        driver.find_element_by_id("id_form-0-title").send_keys("Test Title")
        driver.find_element_by_id("id_form-0-file").send_keys(image_path)
        # Save uploaded image
        with WaitForPageLoad(driver, timeout=50):
            driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added
        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Files updated successfully")
        )

    def test_delete_file_test_level(self):
        # View existing test from ProductTest()
        # Login to the site.
        driver = self.login_page()
        # goto engagemnent list (and wait for javascript to load)
        self.goto_all_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()
        driver.find_element_by_partial_link_text("Pen Test").click()
        driver.find_element_by_name("Manage Files").click()
        # mark delete checkbox for first file input field: form-0-DELETE
        driver.find_element_by_id("id_form-0-DELETE").click()
        # Save selection(s) for image deletion
        driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added
        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Files updated successfully")
        )

    def test_add_file_engagement_level(self):
        # View existing test from ProductTest()
        # Login to the site.
        driver = self.login_page()
        # goto engagemnent list (and wait for javascript to load)
        self.goto_all_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()
        self.uncollapse_all(driver)
        driver.find_element_by_name("Manage Files").click()
        # select first file input field: form-0-image
        # Set full image path for image file 'strange.png
        image_path = os.path.join(dir_path, "finding_image.png")
        driver.find_element_by_id("id_form-0-title").send_keys("Engagement Title")
        driver.find_element_by_id("id_form-0-file").send_keys(image_path)
        # Save uploaded image
        with WaitForPageLoad(driver, timeout=50):
            driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added
        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Files updated successfully")
        )

    def test_delete_file_engagement_level(self):
        # View existing test from ProductTest()
        # Login to the site.
        driver = self.login_page()
        # goto engagemnent list (and wait for javascript to load)
        self.goto_all_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()
        self.uncollapse_all(driver)
        driver.find_element_by_name("Manage Files").click()
        # mark delete checkbox for first file input field: form-0-DELETE
        driver.find_element_by_id("id_form-0-DELETE").click()
        # Save selection(s) for image deletion
        driver.find_element_by_css_selector("button.btn.btn-success").click()
        # Query the site to determine if the finding has been added
        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Files updated successfully")
        )


def add_file_tests_to_suite(suite):
    # Add each test the the suite to be run
    # success and failure is output by the test
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(ProductTest("test_create_product"))
    suite.addTest(ProductTest("test_add_product_finding"))
    suite.addTest(FileUploadTest("test_add_file_finding_level"))
    suite.addTest(FileUploadTest("test_delete_file_finding_level"))
    suite.addTest(FileUploadTest("test_add_file_test_level"))
    suite.addTest(FileUploadTest("test_delete_file_test_level"))
    suite.addTest(FileUploadTest("test_add_file_engagement_level"))
    suite.addTest(FileUploadTest("test_delete_file_engagement_level"))
    suite.addTest(ProductTest("test_delete_product"))

    return suite


def suite():
    suite = unittest.TestSuite()
    add_file_tests_to_suite(suite)
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
