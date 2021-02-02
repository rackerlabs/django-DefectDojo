import unittest
import sys
from base_test_class import BaseTestCase


class SearchTests(BaseTestCase):
    def test_login(self):
        driver = self.driver

    def test_search(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("finding")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_cve(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("cve:CVE-2020-12345")
        driver.find_element_by_id("simple_search_submit").click()

        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("CVE-2020-12345")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_tag(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("tag:magento")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_product_tag(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("product-tag:java")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_engagement_tag(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("engagement-tag:php")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_test_tag(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("test-tag:go")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_tags(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("tags:php")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_product_tags(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("product-tags:java")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_engagement_tags(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("engagement-tags:php")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_test_tags(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("test-tags:go")
        driver.find_element_by_id("simple_search_submit").click()

    def test_search_id(self):
        # very basic search test to see if it doesn't 500
        driver = self.goto_some_page()
        driver.find_element_by_id("simple_search").clear()
        driver.find_element_by_id("simple_search").send_keys("id:1")
        driver.find_element_by_id("simple_search_submit").click()


def suite():
    suite = unittest.TestSuite()
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(SearchTests("test_search"))
    suite.addTest(SearchTests("test_search_cve"))
    suite.addTest(SearchTests("test_search_tag"))
    suite.addTest(SearchTests("test_search_product_tag"))
    suite.addTest(SearchTests("test_search_engagement_tag"))
    suite.addTest(SearchTests("test_search_test_tag"))
    suite.addTest(SearchTests("test_search_tags"))
    suite.addTest(SearchTests("test_search_product_tags"))
    suite.addTest(SearchTests("test_search_engagement_tags"))
    suite.addTest(SearchTests("test_search_test_tags"))
    suite.addTest(SearchTests("test_search_id"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
