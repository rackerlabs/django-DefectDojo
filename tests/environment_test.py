import unittest
import sys
import os
from base_test_class import BaseTestCase


class EnvironmentTest(BaseTestCase):
    def login_page(self):
        driver = self.driver
        driver.get(self.base_url + "login")
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys(os.environ["DD_ADMIN_USER"])
        driver.find_element_by_id("id_password").clear()
        driver.find_element_by_id("id_password").send_keys(
            os.environ["DD_ADMIN_PASSWORD"]
        )
        driver.find_element_by_css_selector("button.btn.btn-success").click()
        return driver

    def test_create_environment(self):
        driver = self.driver
        driver.get(self.base_url + "dev_env")
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_link_text("New Environment").click()
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("environment test")
        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        self.assertTrue(
            self.is_success_message_present(text="Environment added successfully.")
        )

    def test_edit_environment(self):
        driver = self.driver
        driver.get(self.base_url + "dev_env")
        driver.find_element_by_link_text("environment test").click()
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("Edited environment test")
        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        self.assertTrue(
            self.is_success_message_present(text="Environment updated successfully.")
        )

    def test_delete_environment(self):
        driver = self.driver
        driver.get(self.base_url + "dev_env")
        driver.find_element_by_link_text("Edited environment test").click()
        driver.find_element_by_css_selector("input.btn.btn-danger").click()

        self.assertTrue(
            self.is_success_message_present(text="Environment deleted successfully.")
        )


def suite():
    suite = unittest.TestSuite()
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(EnvironmentTest("test_create_environment"))
    suite.addTest(EnvironmentTest("test_edit_environment"))
    suite.addTest(EnvironmentTest("test_delete_environment"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
