import unittest
from base_test_class import BaseTestCase
import sys


class VariousPagesTest(BaseTestCase):
    def test_user_status(self):
        driver = self.driver
        driver.get(self.base_url + "user")

    def test_calendar_status(self):
        driver = self.driver
        driver.get(self.base_url + "calendar")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(VariousPagesTest("test_user_status"))
    suite.addTest(VariousPagesTest("test_calendar_status"))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
