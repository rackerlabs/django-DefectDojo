import unittest
import sys
from base_test_class import BaseTestCase, on_exception_html_source_logger


class ProductTypeTest(BaseTestCase):
    @on_exception_html_source_logger
    def test_create_product_type(self):
        print("\n\nDebug Print Log: testing 'create product type' \n")
        driver = self.driver
        driver.get(self.base_url + "product/type")
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_link_text("Add Product Type").click()
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("product test type")
        driver.find_element_by_id("id_critical_product").click()
        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        self.assertTrue(
            self.is_success_message_present(text="Product type added successfully.")
        )
        self.assertFalse(self.is_error_message_present())

    @on_exception_html_source_logger
    def test_create_product_for_product_type(self):
        # make sure no left overs from previous runs are left behind
        self.delete_product_if_exists("QA Test PT")

        driver = self.driver
        # Navigate to the product page
        self.goto_product_type_overview(driver)

        driver.find_element_by_id("dropdownMenuProductType").click()
        driver.find_element_by_partial_link_text("Add Product").click()
        # Fill in th product name
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("QA Test PT")
        # Tab into the description area to fill some text
        # Couldnt find a way to get into the box with selenium
        driver.find_element_by_id("id_name").send_keys(
            "\tThis is just a test. Be very afraid."
        )
        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        # Assert ot the query to dtermine status of failure
        # Also confirm success even if Product is returned as already exists for test sake
        self.assertTrue(
            self.is_success_message_present(text="Product added successfully")
        )
        self.assertFalse(self.is_error_message_present())

    def test_view_product_type(self):
        print("\n\nDebug Print Log: testing 'view product type' \n")
        driver = self.driver
        driver.get(self.base_url + "product/type")
        driver.find_element_by_id("dropdownMenuProductType").click()
        driver.find_element_by_partial_link_text("View").click()
        product_type_text = driver.find_element_by_id("id_heading").text

        self.assertEqual("Product Type product test type", product_type_text)

    def test_edit_product_type(self):
        print("\n\nDebug Print Log: testing 'edit product type' \n")
        driver = self.driver
        driver.get(self.base_url + "product/type")
        driver.find_element_by_id("dropdownMenuProductType").click()
        driver.find_element_by_partial_link_text("Edit").click()
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("Edited product test type")
        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        self.assertTrue(
            self.is_success_message_present(text="Product type updated successfully.")
        )

    def test_delete_product_type(self):
        print("\n\nDebug Print Log: testing 'delete product type' \n")
        driver = self.driver
        driver.get(self.base_url + "product/type")
        # TODO this assumes the first product_type in the list is the one that we just created (and can safely be deleted)
        driver.find_element_by_id("dropdownMenuProductType").click()
        driver.find_element_by_partial_link_text("Delete").click()
        driver.find_element_by_css_selector("button.btn.btn-danger").click()

        self.assertTrue(
            self.is_success_message_present(
                text="Product Type and relationships removed."
            )
        )


def suite():
    suite = unittest.TestSuite()
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(ProductTypeTest("test_create_product_type"))
    suite.addTest(ProductTypeTest("test_view_product_type"))
    suite.addTest(ProductTypeTest("test_create_product_for_product_type"))
    suite.addTest(ProductTypeTest("test_edit_product_type"))
    suite.addTest(ProductTypeTest("test_delete_product_type"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
