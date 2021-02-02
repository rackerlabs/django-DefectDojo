from selenium.webdriver.support.ui import Select
import unittest
import sys
from base_test_class import BaseTestCase
from product_test import ProductTest


class TestUnitTest(BaseTestCase):
    def test_view_test(self):
        # View existing test from ProductTest()
        # Login to the site.
        driver = self.driver

        # goto engagemnent list (and wait for javascript to load)
        self.goto_all_engagements_overview(driver)

        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()

        driver.find_element_by_partial_link_text("Pen Test").click()

        driver.find_element_by_id("select_all").click()

        # bulk edit dropdown menu
        driver.find_element_by_id("dropdownMenu2").click()

        bulk_edit_menu = driver.find_element_by_id("bulk_edit_menu")
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_active").is_enabled(), False
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_verified").is_enabled(), False
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_false_p").is_enabled(), False
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_out_of_scope").is_enabled(),
            False,
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_is_Mitigated").is_enabled(),
            False,
        )

        driver.find_element_by_id("id_bulk_status").click()

        bulk_edit_menu = driver.find_element_by_id("bulk_edit_menu")
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_active").is_enabled(), True
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_verified").is_enabled(), True
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_false_p").is_enabled(), True
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_out_of_scope").is_enabled(), True
        )
        self.assertEqual(
            bulk_edit_menu.find_element_by_id("id_bulk_is_Mitigated").is_enabled(), True
        )

    def test_create_test(self):
        # To create test for a product
        # You must have an engagement and then tests are packed in engagements
        # Login to the site.
        # Username and password will be gotten from environ
        driver = self.driver
        # Navigate to the Product page to select the product we created earlier
        self.goto_product_overview(driver)
        # wait for product_wrapper div as datatables javascript modifies the DOM on page load.
        driver.find_element_by_id("products_wrapper")
        # Select and click on the particular product to create test for
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on the 'Engagement' Dropdown button
        driver.find_element_by_partial_link_text("Engagement").click()
        # 'click' the Add New Engagement option
        driver.find_element_by_link_text("Add New Engagement").click()
        # Keep a good practice of clearing field before entering value
        # fill up at least all required input field options.
        # fields: 'Name', 'Description', 'Target Start', 'Target End', 'Testing Lead' and 'Status'
        # engagement name
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("Beta Test")
        # engagement description
        # Tab into the description area to fill some text
        # Couldnt find a way to get into the box with selenium
        driver.find_element_by_id("id_name").send_keys(
            "\tRunning Test on product before approving and push to production."
        )
        # engagement target start and target end already have defaults
        # we can safely skip
        # Testing Lead: This can be the logged in user
        Select(driver.find_element_by_id("id_lead")).select_by_visible_text("admin")
        # engagement status
        Select(driver.find_element_by_id("id_status")).select_by_visible_text(
            "In Progress"
        )
        # "Click" the 'Add Test' button to Add Test to engagement
        driver.find_element_by_name("_Add Tests").click()
        # Fill at least required fields needed to create Test
        # Test title
        driver.find_element_by_id(
            "id_title"
        ).clear()  # clear field before inserting anything
        driver.find_element_by_id("id_title").send_keys("Quick Security Testing")
        # Select Test type
        Select(driver.find_element_by_id("id_test_type")).select_by_visible_text(
            "Manual Code Review"
        )
        # skip Target start and Target end leaving their default values
        # Select Testing Environment
        Select(driver.find_element_by_id("id_environment")).select_by_visible_text(
            "Development"
        )
        # submit
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the Test has been added

        # Assert on the query to determine success or failure
        self.assertTrue(self.is_success_message_present(text="Test added successfully"))

    def test_edit_test(self):
        # Login to the site.
        driver = self.driver
        # Navigate to the engagement page
        self.goto_active_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Quick Security Testing").click()
        # "Click" the dropdown button to see options
        driver.find_element_by_id("dropdownMenu1").click()
        # "Click" the Edit Test option
        driver.find_element_by_link_text("Edit Test").click()
        # Change Testing Environment to Staging from Development
        Select(driver.find_element_by_id("id_environment")).select_by_visible_text(
            "Staging"
        )
        # "Click" the submit button to complete the transaction
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the Test has been updated

        # Assert ot the query to dtermine status of failure
        self.assertTrue(self.is_success_message_present(text="Test saved."))

    def test_add_note(self):
        # Login to the site.
        driver = self.driver
        # Navigate to the engagement page
        self.goto_active_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Quick Security Testing").click()
        # "Click" the dropdown button to see options
        driver.find_element_by_id("dropdownMenu1").click()
        # "Click" the Edit Test option
        driver.find_element_by_link_text("Add Notes").click()
        # Select entry, clear field and input note
        driver.find_element_by_id("id_entry").clear()
        driver.find_element_by_id("id_entry").send_keys(
            "This is a sample note for all to see."
        )
        # "Click" the submit button to complete the transaction
        driver.find_element_by_xpath("//input[@value='Add Note']").click()
        # Query the site to determine if the Test has been updated

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Note added successfully.")
        )

    def test_delete_test(self):
        # Login to the site. Password will have to be modified
        # to match an admin password in your own container
        driver = self.driver
        # Navigate to the engagement page
        self.goto_active_engagements_overview(driver)
        # Select a previously created engagement title
        driver.find_element_by_partial_link_text("Quick Security Testing").click()
        # "Click" the dropdown button to see options
        driver.find_element_by_id("dropdownMenu1").click()
        # "Click" the Edit Test option
        driver.find_element_by_link_text("Delete Test").click()
        # Type test name into Title field before clicking Delet button
        driver.find_element_by_id("id_title").clear()  # always clear for inputting
        driver.find_element_by_id("id_title").send_keys("Quick Security Testing")
        # "Click" the delete button to complete the transaction
        driver.find_element_by_css_selector("button.btn.btn-danger").click()
        # Query the site to determine if the product has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Test and relationships removed.")
        )


def suite():
    suite = unittest.TestSuite()
    # Add each test the the suite to be run
    # success and failure is output by the test
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(ProductTest("test_create_product"))
    suite.addTest(ProductTest("test_add_product_finding"))
    suite.addTest(TestUnitTest("test_view_test"))
    suite.addTest(TestUnitTest("test_create_test"))
    suite.addTest(TestUnitTest("test_edit_test"))
    # suite.addTest(TestUnitTest('test_add_note'))
    # suite.addTest(TestUnitTest('test_delete_test'))
    suite.addTest(ProductTest("test_delete_product"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
