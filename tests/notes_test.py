import unittest
import sys
import time
from base_test_class import BaseTestCase
from product_test import ProductTest

"""
Tests Notes functionality on all levels (Engagement, Test, and Finding)
Private and public notes are tested
"""


class NoteTest(BaseTestCase):
    def uncollapse_all(self, driver):
        elems = driver.find_elements_by_name("collapsible")
        for elem in elems:
            elem.click()
            time.sleep(0.5)
        return driver

    def create_public_note(self, driver, level):
        time.sleep(1)
        if not driver.find_element_by_id("add_note").is_displayed():
            self.uncollapse_all(driver)
        driver.find_element_by_id("id_entry").send_keys("Test public note")
        driver.find_element_by_id("add_note").click()
        time.sleep(1)
        if not driver.find_element_by_id("add_note").is_displayed():
            self.uncollapse_all(driver)
        text = driver.find_element_by_tag_name("body").text
        pass_test = "Test public note" in text
        if not pass_test:
            print("Public note created at the", level, "level")
        self.assertTrue(pass_test)

    def create_private_note(self, driver, level):
        time.sleep(1)
        if not driver.find_element_by_id("add_note").is_displayed():
            self.uncollapse_all(driver)
        driver.find_element_by_id("id_entry").send_keys("Test private note")
        driver.find_element_by_id("id_private").click()
        driver.find_element_by_id("add_note").click()
        time.sleep(1)
        if not driver.find_element_by_id("add_note").is_displayed():
            self.uncollapse_all(driver)
        text = driver.find_element_by_tag_name("body").text
        note_present = "Test public note" in text
        private_status = "(will not appear in report)" in text
        pass_test = note_present and private_status
        if not pass_test:
            print("Private note note created at the", level, "level")
        self.assertTrue(pass_test)

    def test_finding_note(self):
        driver = self.driver
        self.goto_all_findings_list(driver)
        driver.find_element_by_link_text("App Vulnerable to XSS").click()
        self.create_public_note(driver, "Finding")
        self.create_private_note(driver, "Finding")

    def test_test_note(self):
        driver = self.driver
        self.goto_all_engagements_overview(driver)
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()
        driver.find_element_by_partial_link_text("Pen Test").click()
        self.create_public_note(driver, "Test")
        self.create_private_note(driver, "Test")

    def test_engagement_note(self):
        driver = self.driver
        self.goto_all_engagements_overview(driver)
        driver.find_element_by_partial_link_text("Ad Hoc Engagement").click()
        self.create_public_note(driver, "Engagement")
        self.create_private_note(driver, "Engagement")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(ProductTest("test_create_product"))
    suite.addTest(ProductTest("test_add_product_finding"))
    suite.addTest(NoteTest("test_finding_note"))
    suite.addTest(NoteTest("test_test_note"))
    suite.addTest(NoteTest("test_engagement_note"))
    suite.addTest(ProductTest("test_delete_product"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
