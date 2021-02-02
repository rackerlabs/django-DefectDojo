from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
import unittest
import sys
import time
from base_test_class import BaseTestCase, on_exception_html_source_logger


class WaitForPageLoad(object):
    def __init__(self, browser, timeout):
        self.browser = browser
        self.timeout = time.time() + timeout

    def __enter__(self):
        self.old_page = self.browser.find_element_by_tag_name("html")

    def page_has_loaded(self):
        new_page = self.browser.find_element_by_tag_name("html")
        return new_page.id != self.old_page.id

    def __exit__(self, *_):
        while time.time() < self.timeout:
            if self.page_has_loaded():
                return True
            else:
                time.sleep(0.2)
        raise Exception("Timeout waiting for {}s".format(self.timeout))


class ProductTest(BaseTestCase):
    @on_exception_html_source_logger
    def test_create_product(self):
        # make sure no left overs from previous runs are left behind
        self.delete_product_if_exists()

        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # "Click" the dropdown button to see options
        driver.find_element_by_id("dropdownMenu1").click()
        # "Click" the add prodcut button
        driver.find_element_by_link_text("Add Product").click()
        # Fill in th product name
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("QA Test")
        # Tab into the description area to fill some text
        # Couldnt find a way to get into the box with selenium
        driver.find_element_by_id("id_name").send_keys(
            "\tThis is just a test. Be very afraid."
        )
        # Select an option in the poroduct type
        # some wild guess to print some debug info
        Select(driver.find_element_by_id("id_prod_type")).select_by_visible_text(
            "Research and Development"
        )
        # "Click" the submit button to complete the transaction
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the product has been added

        # Assert ot the query to dtermine status of failure
        # Also confirm success even if Product is returned as already exists for test sake
        self.assertTrue(
            self.is_success_message_present(text="Product added successfully")
            or self.is_success_message_present(
                text="Product with this Name already exists."
            )
        )
        self.assertFalse(self.is_error_message_present())

    @on_exception_html_source_logger
    def test_list_products(self):
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # list products which will make sure there are no javascript errors such as before in https://github.com/DefectDojo/django-DefectDojo/issues/2050

    @on_exception_html_source_logger
    def test_list_components(self):
        driver = self.driver
        self.goto_product_overview(driver)
        driver.find_element_by_link_text("QA Test").click()
        driver.find_element_by_link_text("Components").click()
        driver.find_element_by_id("product_component_view").click()
        self.assertTrue(self.is_element_by_css_selector_present("table"))

    # For product consistency sake, We won't be editting the product title
    # instead We can edit the product description
    @on_exception_html_source_logger
    def test_edit_product_description(self):
        # Login to the site. Password will have to be modified
        # to match an admin password in your own container
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        # driver.execute_script("window.scrollTo(0, 0)")
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on the 'Edit' option
        driver.find_element_by_link_text("Edit").click()
        # Edit product description
        driver.find_element_by_id("id_name").send_keys(Keys.TAB, "Updated Desription: ")
        # "Click" the submit button to complete the transaction
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the product has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Product updated successfully")
            or self.is_success_message_present(
                text="Product with this Name already exists."
            )
        )
        self.assertFalse(self.is_error_message_present())

    @on_exception_html_source_logger
    def test_add_product_engagement(self):
        # Test To Add Engagement To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        driver.find_element_by_id("dropdownMenu1").click()
        # Click on the 'Engagement dropdown button'
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
            Keys.TAB, "Running Test on product before approving and push to production."
        )
        # engagement target start and target end already have defaults
        # we can safely skip
        # Testing Lead: This can be the logged in user
        Select(driver.find_element_by_id("id_lead")).select_by_visible_text("admin")
        # engagement status
        Select(driver.find_element_by_id("id_status")).select_by_visible_text(
            "In Progress"
        )
        # "Click" the Done button to Add the engagement
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the product has been added

        # Assert of the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Engagement added successfully")
        )

    @on_exception_html_source_logger
    def test_add_product_finding(self):
        # Test To Add Finding To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # Click on the 'Finding dropdown button'
        driver.find_element_by_partial_link_text("Findings").click()
        # Click on `Add New Finding`
        driver.find_element_by_link_text("Add New Finding").click()
        # Keep a good practice of clearing field before entering value
        # fill up at least all required input field options.
        # fields: 'Title', 'Date', 'Severity', 'Description', 'Mitigation' and 'Impact'
        # finding Title
        driver.find_element_by_id("id_title").clear()
        driver.find_element_by_id("id_title").send_keys("App Vulnerable to XSS")
        # finding Date as a default value and can be safely skipped
        # finding Severity
        Select(driver.find_element_by_id("id_severity")).select_by_visible_text("High")
        # finding Description
        driver.find_element_by_id("id_severity").send_keys(
            Keys.TAB, "This is just a Test Case Finding"
        )
        # Finding Mitigation
        # Use Javascript to bypass the editor by making Setting textArea style from none to inline
        # Any Text written to textarea automatically reflects in Editor field.
        driver.execute_script(
            "document.getElementsByName('mitigation')[0].style.display = 'inline'"
        )
        driver.find_element_by_name("mitigation").send_keys(
            Keys.TAB, "How to mitigate this finding"
        )
        # Finding Impact
        # Use Javascript to bypass the editor by making Setting textArea style from none to inline
        # Any Text written to textarea automatically reflects in Editor field.
        driver.execute_script(
            "document.getElementsByName('impact')[0].style.display = 'inline'"
        )
        driver.find_element_by_name("impact").send_keys(
            Keys.TAB, "This has a very critical effect on production"
        )
        # Add an endpoint
        main_window_handle = driver.current_window_handle
        driver.find_element_by_id("add_id_endpoints").click()
        popup_window = None
        while not popup_window:
            for handle in driver.window_handles:
                if handle != main_window_handle:
                    popup_window = handle
                    break
        driver.switch_to.window(popup_window)
        driver.find_element_by_id("id_endpoint").clear()
        driver.find_element_by_id("id_endpoint").send_keys("product.finding.com")
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        driver.switch_to.window(main_window_handle)
        # "Click" the Done button to Add the finding with other defaults
        with WaitForPageLoad(driver, timeout=30):
            driver.find_element_by_xpath("//input[@name='_Finished']").click()
        # Query the site to determine if the finding has been added

        # Assert to the query to dtermine status of failure
        self.assertTrue(self.is_text_present_on_page(text="App Vulnerable to XSS"))

    @on_exception_html_source_logger
    def test_add_product_endpoints(self):
        # Test To Add Endpoints To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # Click on the 'Endpoints' dropdown button
        driver.find_element_by_partial_link_text("Endpoints").click()
        # 'click' the Add New Endpoint option
        driver.find_element_by_link_text("Add New Endpoint").click()
        # Keep a good practice of clearing field before entering value
        # Endpoints
        driver.find_element_by_id("id_endpoint").clear()
        driver.find_element_by_id("id_endpoint").send_keys(
            "strange.prod.dev\n123.45.6.30"
        )
        # submit
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Endpoint added successfully")
        )

    @on_exception_html_source_logger
    def test_add_product_custom_field(self):
        # Test To Add Custom Fields To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        driver.find_element_by_id("dropdownMenu1").click()
        # 'click' the Add Custom Fields
        driver.find_element_by_link_text("Add Custom Fields").click()
        # Keep a good practice of clearing field before entering value
        # Custom Name
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("Security Level")
        # Custom Value
        driver.find_element_by_id("id_value").clear()
        driver.find_element_by_id("id_value").send_keys("Loose")
        # submit
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        # Also confirm success even if variable is returned as already exists for test sake
        self.assertTrue(
            self.is_success_message_present(text="Metadata added successfully")
            or self.is_success_message_present(
                text="A metadata entry with the same name exists already for this object."
            )
        )

    @on_exception_html_source_logger
    def test_edit_product_custom_field(self):
        # Test To Edit Product Custom Fields
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        driver.find_element_by_id("dropdownMenu1").click()
        # 'click' the Edit Custom Fields
        driver.find_element_by_link_text("Edit Custom Fields").click()
        # Keep a good practice of clearing field before entering value
        # Edit Custom Value of First field
        driver.find_element_by_xpath("//input[@value='Loose']").clear()
        driver.find_element_by_xpath("//input[@value='Loose']").send_keys("Strong")
        # submit
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine success or failure
        self.assertTrue(
            self.is_success_message_present(text="Metadata edited successfully")
            or self.is_success_message_present(
                text="A metadata entry with the same name exists already for this object."
            )
        )

    @on_exception_html_source_logger
    def test_add_product_tracking_files(self):
        # Test To Add tracking files To product
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        driver.find_element_by_id("dropdownMenu1").click()
        # 'click' the Add Product Tracking Files
        driver.find_element_by_link_text("Add Product Tracking Files").click()
        # Keep a good practice of clearing field before entering value
        # Just fill up to main required fields: 'File path' nd 'review status'
        # Full File path
        driver.find_element_by_id("id_path").clear()
        driver.find_element_by_id("id_path").send_keys("/strange/folder/")
        # REview Status
        Select(driver.find_element_by_id("id_review_status")).select_by_visible_text(
            "Untracked"
        )
        # submit
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the finding has been added

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Added Tracked File to a Product")
        )

    @on_exception_html_source_logger
    def test_edit_product_tracking_files(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        driver.find_element_by_id("dropdownMenu1").click()
        # 'click' the Edit Product Tracking Files
        driver.find_element_by_link_text("View Product Tracking Files").click()
        # Keep a good practice of clearing field before entering value
        # Edit Custom Value of First field
        driver.find_element_by_link_text("Edit").click()
        # Edit full file path
        driver.find_element_by_id("id_path").clear()
        driver.find_element_by_id("id_path").send_keys("/unknown/folder/")
        # submit
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the Tracking file has been updated

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(
                text="Tool Product Configuration Successfully Updated"
            )
        )

    def test_product_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select and click on the particular product to edit
        driver.find_element_by_link_text("QA Test").click()
        # "Click" the dropdown option
        # driver.find_element_by_xpath("//span[contains(., 'Metrics')]").click()
        driver.find_element_by_partial_link_text("Metrics").click()

    @on_exception_html_source_logger
    def test_delete_product(self, name="QA Test"):
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select the specific product to delete
        driver.find_element_by_link_text(name).click()
        # Click the drop down menu
        # driver.execute_script("window.scrollTo(0, 0)")
        driver.find_element_by_id("dropdownMenu1").click()
        # "Click" the Delete option
        driver.find_element_by_link_text("Delete").click()
        # "Click" the delete button to complete the transaction
        driver.find_element_by_css_selector("button.btn.btn-danger").click()
        # Query the site to determine if the product has been added

        # Assert ot the query to determine status of failure
        self.assertTrue(
            self.is_success_message_present(text="Product and relationships removed.")
        )

    @on_exception_html_source_logger
    def test_product_notifications_change(self):
        # Login to the site. Password will have to be modified
        # to match an admin password in your own container
        driver = self.driver
        self.goto_product_overview(driver)
        # Select the specific product to delete
        driver.find_element_by_link_text("QA Test").click()

        driver.find_element_by_xpath(
            "//input[@name='engagement_added' and @value='mail']"
        ).click()
        # clicking == ajax call to submit, but I think selenium gets this

        self.assertTrue(
            self.is_success_message_present(text="Notification settings updated")
        )
        self.assertTrue(
            driver.find_element_by_xpath(
                "//input[@name='engagement_added' and @value='mail']"
            ).is_selected()
        )
        self.assertFalse(
            driver.find_element_by_xpath(
                "//input[@name='scan_added' and @value='mail']"
            ).is_selected()
        )
        self.assertFalse(
            driver.find_element_by_xpath(
                "//input[@name='test_added' and @value='mail']"
            ).is_selected()
        )

        driver.find_element_by_xpath(
            "//input[@name='scan_added' and @value='mail']"
        ).click()

        self.assertTrue(
            self.is_success_message_present(text="Notification settings updated")
        )
        self.assertTrue(
            driver.find_element_by_xpath(
                "//input[@name='engagement_added' and @value='mail']"
            ).is_selected()
        )
        self.assertTrue(
            driver.find_element_by_xpath(
                "//input[@name='scan_added' and @value='mail']"
            ).is_selected()
        )
        self.assertFalse(
            driver.find_element_by_xpath(
                "//input[@name='test_added' and @value='mail']"
            ).is_selected()
        )

    def test_critical_product_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "critical_product_metrics")

    def test_product_type_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "metrics/product/type")

    def test_product_type_counts_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "metrics/product/type/counts")

        my_select = Select(driver.find_element_by_id("id_product_type"))
        my_select.select_by_index(1)

        driver.find_element_by_css_selector("input.btn.btn-primary").click()

    def test_simple_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "metrics/simple")

    def test_engineer_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "metrics/engineer")

    def test_security_research_metrics(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "metrics/research")

    def test_metrics_dashboard(self):
        # Test To Edit Product Tracking Files
        # login to site, password set to fetch from environ
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "metrics?date=5&view=dashboard")


def add_product_tests_to_suite(suite):
    # Add each test and the suite to be run
    # success and failure is output by the test
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(ProductTest("test_create_product"))
    suite.addTest(ProductTest("test_edit_product_description"))
    suite.addTest(ProductTest("test_add_product_engagement"))
    suite.addTest(ProductTest("test_add_product_finding"))
    suite.addTest(ProductTest("test_add_product_endpoints"))
    suite.addTest(ProductTest("test_add_product_custom_field"))
    suite.addTest(ProductTest("test_edit_product_custom_field"))
    suite.addTest(ProductTest("test_add_product_tracking_files"))
    suite.addTest(ProductTest("test_edit_product_tracking_files"))
    suite.addTest(ProductTest("test_list_products"))
    suite.addTest(ProductTest("test_list_components"))
    suite.addTest(ProductTest("test_product_notifications_change"))
    suite.addTest(ProductTest("test_product_metrics"))

    # we add metrics tests here as we now have a product that triggers some logic inside metrics
    suite.addTest(ProductTest("test_critical_product_metrics"))
    suite.addTest(ProductTest("test_product_type_metrics"))
    suite.addTest(ProductTest("test_product_type_counts_metrics"))
    suite.addTest(ProductTest("test_simple_metrics"))
    suite.addTest(ProductTest("test_engineer_metrics"))
    suite.addTest(ProductTest("test_security_research_metrics"))
    suite.addTest(ProductTest("test_metrics_dashboard"))

    suite.addTest(ProductTest("test_delete_product"))
    return suite


def suite():
    suite = unittest.TestSuite()
    add_product_tests_to_suite(suite)
    suite.addTest(ProductTest("enable_jira"))
    suite.addTest(ProductTest("enable_github"))
    suite.addTest(ProductTest("enable_block_execution"))
    add_product_tests_to_suite(suite)

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
