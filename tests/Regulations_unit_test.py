import unittest
import sys
import os
from base_test_class import BaseTestCase


class RegulationTest(BaseTestCase):

    def login_page(self):
        driver = self.driver
        driver.get(self.base_url + "login")
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys(os.environ['DD_ADMIN_USER'])
        driver.find_element_by_id("id_password").clear()
        driver.find_element_by_id("id_password").send_keys(os.environ['DD_ADMIN_PASSWORD'])
        driver.find_element_by_css_selector("button.btn.btn-success").click()
        return driver

    def test_create_regulation(self):
        driver = self.login_page()
        driver.get(self.base_url + "regulations")
        driver.find_element_by_link_text("Regulations").click()
        driver.find_element_by_id("dropdownMenu1").click()
        driver.find_element_by_link_text("Add regulation").click()
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("PSA_TEST")
        driver.find_element_by_id("id_acronym").clear()
        driver.find_element_by_id("id_acronym").send_keys("PSA_TEST")
        driver.find_element_by_css_selector("option:nth-child(6)").click()
        driver.find_element_by_id("id_jurisdiction").clear()
        driver.find_element_by_id("id_jurisdiction").send_keys("Europe")
        driver.find_element_by_id("id_description").clear()
        driver.find_element_by_id("id_description").send_keys("Few words abot PSA")
        driver.find_element_by_id("id_reference").clear()
        driver.find_element_by_id("id_reference").send_keys("http://www.psa.eu")
        driver.find_element_by_css_selector(".col-sm-offset-2 > .btn").click()

        self.assertTrue(self.is_success_message_present(text='Regulation Successfully Created.'))
    '''
    def test_edit_environment(self):
        driver = self.login_page()
        driver.get(self.base_url + "dev_env")
        driver.find_element_by_link_text("environment test").click()
        driver.find_element_by_id("id_name").clear()
        driver.find_element_by_id("id_name").send_keys("Edited environment test")
        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        self.assertTrue(self.is_success_message_present(text='Regulation Successfully Created.'))

    def test_delete_environment(self):
        driver = self.login_page()
        driver.get(self.base_url + "dev_env")
        driver.find_element_by_link_text("Edited environment test").click()
        driver.find_element_by_css_selector("input.btn.btn-danger").click()

        self.assertTrue(self.is_success_message_present(text='Environment deleted successfully.'))
    '''

def suite():
    suite = unittest.TestSuite()
    suite.addTest(RegulationTest('test_create_regulation'))
    # suite.addTest(EnvironmentTest('test_edit_environment'))
    # suite.addTest(EnvironmentTest('test_delete_environment'))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
