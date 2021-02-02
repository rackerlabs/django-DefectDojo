# from selenium.webdriver.support.ui import Select
import unittest
import sys
from base_test_class import BaseTestCase
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains


class UserTest(BaseTestCase):
    def test_create_user(self):
        # Login to the site.
        driver = self.driver
        # Navigate to the User managegement page
        driver.get(self.base_url + "user")
        # "Click" the dropdown button to see options
        driver.find_element_by_id("dropdownMenu1").click()
        # "Click" the add prodcut button
        driver.find_element_by_link_text("New User").click()
        # Fill in the Necessary User Details
        # username, first name, last name, email, and permissions
        # Don't forget to clear before inserting
        # username
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("propersahm")
        # First Name
        driver.find_element_by_id("id_first_name").clear()
        driver.find_element_by_id("id_first_name").send_keys("Proper")
        # Last Name
        driver.find_element_by_id("id_last_name").clear()
        driver.find_element_by_id("id_last_name").send_keys("Samuel")
        # Email Address
        driver.find_element_by_id("id_email").clear()
        driver.find_element_by_id("id_email").send_keys("propersam@example.com")
        # Give user super user permissions by ticking the checkbox 'is_superuser'
        driver.find_element_by_name(
            "is_superuser"
        ).click()  # Clicking will mark the checkbox
        # "Click" the submit button to complete the transaction
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the user has been created

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(
                text="User added successfully, you may edit if necessary."
            )
            or self.is_success_message_present(
                text="A user with that username already exists."
            )
        )

    def test_user_edit_permissions(self):
        # Login to the site. Password will have to be modified
        # to match an admin password in your own container
        driver = self.driver
        # Navigate to User Management page
        driver.get(self.base_url + "user")
        # Select the previously created user to edit
        # The User name is not clickable
        # so we would have to select specific user by filtering list of users
        driver.find_element_by_id("show-filters").click()  # open d filters
        # Insert username to filter by into user name box
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("propersahm")
        # click on 'apply filter' button
        driver.find_element_by_css_selector("button.btn.btn-sm.btn-primary").click()
        # only the needed user is now available proceed with clicking 'Edit' button
        driver.find_element_by_link_text("Edit").click()
        # Unselect Super Admin Permission from previously created user
        # and only select Staff Permission
        driver.find_element_by_name("is_superuser").click()
        driver.find_element_by_name("is_staff").click()
        # "Click" the submit button to complete the transaction
        driver.find_element_by_css_selector("input.btn.btn-primary").click()
        # Query the site to determine if the User permission has been changed

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="User saved successfully.")
        )

    def test_user_delete(self):
        # Login to the site. Password will have to be modified
        # to match an admin password in your own container
        driver = self.driver
        # Navigate to the product page
        driver.get(self.base_url + "user")
        # Select A user to edit
        # The User name is not clickable
        # so we would have to select specific user by filtering list of users
        driver.find_element_by_id("show-filters").click()  # open d filters
        # Insert username to filter by into user name box
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("propersahm")
        # click on 'apply filter' button
        driver.find_element_by_css_selector("button.btn.btn-sm.btn-primary").click()
        # only the needed user is now available proceed with clicking 'Edit' button
        driver.find_element_by_link_text("Edit").click()
        # "Click" the delete button to complete the transaction
        driver.find_element_by_css_selector("a.btn.btn-danger").click()
        # confirm deletion, by clicking delete a second time
        driver.find_element_by_css_selector("button.btn.btn-danger").click()
        # Query the site to determine if the User has been deleted

        # Assert ot the query to dtermine status of failure
        self.assertTrue(
            self.is_success_message_present(text="User and relationships removed.")
        )

    def test_user_notifications_change(self):
        # Login to the site. Password will have to be modified
        # to match an admin password in your own container
        driver = self.driver

        wait = WebDriverWait(driver, 5)
        actions = ActionChains(driver)
        configuration_menu = driver.find_element_by_id("menu_configuration")
        actions.move_to_element(configuration_menu).perform()
        wait.until(
            EC.visibility_of_element_located((By.LINK_TEXT, "Notifications"))
        ).click()

        driver.find_element_by_xpath(
            "//input[@name='product_added' and @value='mail']"
        ).click()
        driver.find_element_by_xpath(
            "//input[@name='scan_added' and @value='mail']"
        ).click()

        driver.find_element_by_css_selector("input.btn.btn-primary").click()

        self.assertTrue(self.is_success_message_present(text="Settings saved"))
        self.assertTrue(
            driver.find_element_by_xpath(
                "//input[@name='product_added' and @value='mail']"
            ).is_selected()
        )
        self.assertTrue(
            driver.find_element_by_xpath(
                "//input[@name='scan_added' and @value='mail']"
            ).is_selected()
        )


def suite():
    suite = unittest.TestSuite()
    # Add each test the the suite to be run
    # success and failure is output by the test
    suite.addTest(BaseTestCase("test_login"))
    suite.addTest(UserTest("test_create_user"))
    suite.addTest(UserTest("test_user_edit_permissions"))
    suite.addTest(UserTest("test_user_delete"))

    # not really for the user we created, but still related to user settings
    suite.addTest(UserTest("test_user_notifications_change"))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(descriptions=True, failfast=True, verbosity=2)
    ret = not runner.run(suite()).wasSuccessful()
    BaseTestCase.tearDownDriver()
    sys.exit(ret)
