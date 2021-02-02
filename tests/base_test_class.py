from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoAlertPresentException

import unittest
import os
import re

# import time

dd_driver = None
dd_driver_options = None


def on_exception_html_source_logger(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)

        except Exception as e:
            print("exception occured at url:", self.driver.current_url)
            print("page source:", self.driver.page_source)
            f = open("selenium_page_source.html", "w", encoding="utf-8")
            f.writelines(self.driver.page_source)
            # time.sleep(30)
            raise (e)

    return wrapper


class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global dd_driver
        if not dd_driver:
            # setupModule and tearDownModule are not working in our scenario, so for now we use setupClass and a global variable
            # global variables are dirty, but in unit tests scenario's like these they are acceptable
            print("launching browser for: ", cls.__name__)
            global dd_driver_options
            dd_driver_options = Options()

            # headless means no UI, if you want to see what is happening remove headless. Adding detach will leave the window open after the test
            dd_driver_options.add_argument("--headless")
            # dd_driver_options.add_experimental_option("detach", True)

            # the next 2 maybe needed in some scenario's for example on WSL or other headless situations
            dd_driver_options.add_argument("--no-sandbox")
            dd_driver_options.add_argument("--disable-dev-shm-usage")
            dd_driver_options.add_argument(
                "--disable-gpu"
            )  # on windows sometimes chrome can't start with certain gpu driver versions, even in headless mode

            # start maximized or at least with sufficient with because datatables will hide certain controls when the screen is too narrow
            dd_driver_options.add_argument("--window-size=1280,1024")
            # dd_driver_options.add_argument("--start-maximized")

            dd_driver_options.set_capability("acceptInsecureCerts", True)

            # some extra logging can be turned on if you want to query the browser javascripe console in your tests
            desired = webdriver.DesiredCapabilities.CHROME
            desired["goog:loggingPrefs"] = {"browser": "ALL"}

            # change path of chromedriver according to which directory you have chromedriver.
            print(
                "starting chromedriver with options: ", vars(dd_driver_options), desired
            )
            dd_driver = webdriver.Chrome(
                "chromedriver",
                chrome_options=dd_driver_options,
                desired_capabilities=desired,
            )
            # best practice is only use explicit waits
            dd_driver.implicitly_wait(1)

        cls.driver = dd_driver
        cls.base_url = os.environ["DD_BASE_URL"]

    def setUp(self):
        self.verificationErrors = []
        self.accept_next_alert = True
        self.accept_javascript_errors = False
        self.driver.execute_script("console.clear()")
        # clear browser console logs?

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

        self.assertFalse(
            self.is_element_by_css_selector_present(
                ".alert-danger", "Please enter a correct username and password"
            )
        )
        return driver

    def test_login(self):
        return self.login_page()

    @on_exception_html_source_logger
    def delete_product_if_exists(self, name="QA Test"):
        driver = self.driver
        # Navigate to the product page
        self.goto_product_overview(driver)
        # Select the specific product to delete
        qa_products = driver.find_elements(By.LINK_TEXT, name)

        if len(qa_products) > 0:
            self.test_delete_product(name)

    # used to load some page just to get started
    # we choose /user because it's lightweight and fast
    def goto_some_page(self):
        driver = self.driver
        driver.get(self.base_url + "user")
        return driver

    def goto_product_overview(self, driver):
        driver.get(self.base_url + "product")
        self.wait_for_datatable_if_content("no_products", "products_wrapper")
        return driver

    def goto_product_type_overview(self, driver):
        driver.get(self.base_url + "product/type")
        return driver

    def goto_component_overview(self, driver):
        driver.get(self.base_url + "components")
        return driver

    def goto_active_engagements_overview(self, driver):
        # return self.goto_engagements_internal(driver, 'engagement')
        # engagement overview doesn't seem to have the datatables yet modifying the DOM
        # https://github.com/DefectDojo/django-DefectDojo/issues/2173
        driver.get(self.base_url + "engagement")
        # self.goto_engagements_internal(driver, 'engagement')
        return driver

    def goto_all_engagements_overview(self, driver):
        return self.goto_engagements_internal(driver, "engagements_all")

    def goto_engagements_internal(self, driver, rel_url):
        driver.get(self.base_url + rel_url)
        self.wait_for_datatable_if_content("no_engagements", "engagements_wrapper")
        return driver

    def goto_all_findings_list(self, driver):
        driver.get(self.base_url + "finding")
        self.wait_for_datatable_if_content("no_findings", "open_findings_wrapper")
        return driver

    def wait_for_datatable_if_content(self, no_content_id, wrapper_id):
        no_content = None
        try:
            no_content = self.driver.find_element_by_id(no_content_id)
        except:
            pass

        if no_content is None:
            # wait for product_wrapper div as datatables javascript modifies the DOM on page load.
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, wrapper_id))
            )

    def is_element_by_css_selector_present(self, selector, text=None):
        elems = self.driver.find_elements_by_css_selector(selector)
        if len(elems) == 0:
            # print('no elements!')
            return False

        if text is None:
            return True

        for elem in elems:
            print(elem.text)
            if text in elem.text:
                # print('contains!')
                return True

        # print('text mismatch!')
        return False

    def is_success_message_present(self, text=None):
        return self.is_element_by_css_selector_present(".alert-success", text=text)

    def is_error_message_present(self, text=None):
        return self.is_element_by_css_selector_present(".alert-danger", text=text)

    def is_text_present_on_page(self, text):
        # DEBUG: couldn't find:  Product type added successfully. path:  //*[contains(text(),'Product type added successfully.')]
        # can't get this xpath to work
        # path = "//*[contains(text(), '" + text + "')]"
        # elems = self.driver.find_elements_by_xpath(path)
        # if len(elems) == 0:
        #     print("DEBUG: couldn't find: ", text, "path: ", path)

        body = self.driver.find_element_by_tag_name("body")
        return re.search(text, body.text)

    def element_exists_by_id(self, id):
        elems = self.driver.find_elements_by_id(id)
        return len(elems) > 0

    def change_system_setting(self, id, enable=True):
        print("changing system setting " + id + " enable: " + str(enable))
        driver = self.driver
        driver.get(self.base_url + "system_settings")

        is_enabled = driver.find_element_by_id(id).is_selected()
        if (enable and not is_enabled) or (not enable and is_enabled):
            # driver.find_element_by_xpath('//*[@id=' + id + ']').click()
            driver.find_element_by_id(id).click()
            # save settings
            driver.find_element_by_css_selector("input.btn.btn-primary").click()
            # check if it's enabled after reload

        is_enabled = driver.find_element_by_id(id).is_selected()

        if enable:
            self.assertTrue(is_enabled)

        if not enable:
            self.assertFalse(is_enabled)

        return is_enabled

    def enable_system_setting(self, id):
        return self.change_system_setting(id, enable=True)

    def disable_system_setting(self, id):
        return self.change_system_setting(id, enable=False)

    def enable_jira(self):
        return self.enable_system_setting("id_enable_jira")

    def disable_jira(self):
        return self.disable_system_setting("id_enable_jira")

    def disable_github(self):
        return self.disable_system_setting("id_enable_github")

    def enable_github(self):
        return self.enable_system_setting("id_enable_github")

    def enable_block_execution(self):
        # we set the admin user (ourselves) to have block_execution checked
        # this will force dedupe to happen synchronously, among other things like notifications, rules, ...
        driver = self.driver
        driver.get(self.base_url + "profile")
        if not driver.find_element_by_id("id_block_execution").is_selected():
            driver.find_element_by_xpath('//*[@id="id_block_execution"]').click()
            # save settings
            driver.find_element_by_css_selector("input.btn.btn-primary").click()
            # check if it's enabled after reload
            self.assertTrue(
                driver.find_element_by_id("id_block_execution").is_selected()
            )
        return driver

    def is_alert_present(self):
        try:
            self.driver.switch_to_alert()
        except NoAlertPresentException:
            return False
        return True

    def close_alert_and_get_its_text(self):
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally:
            self.accept_next_alert = True

    def assertNoConsoleErrors(self):
        """
        Sample output for levels (i.e. errors are SEVERE)
        {'level': 'DEBUG', 'message': 'http://localhost:8080/product/type/4/edit 560:12 "debug"', 'source': 'console-api', 'timestamp': 1583952828410}
        {'level': 'INFO', 'message': 'http://localhost:8080/product/type/4/edit 561:16 "info"', 'source': 'console-api', 'timestamp': 1583952828410}
        {'level': 'WARNING', 'message': 'http://localhost:8080/product/type/4/edit 562:16 "warning"', 'source': 'console-api', 'timestamp': 1583952828410}
        {'level': 'SEVERE', 'message': 'http://localhost:8080/product/type/4/edit 563:16 "error"', 'source': 'console-api', 'timestamp': 1583952828410}
        """

        for entry in WebdriverOnlyNewLogFacade(self.driver).get_log("browser"):
            """
            images are not working in current docker/travis deployment, so ignore those 404s
            see: https://github.com/DefectDojo/django-DefectDojo/issues/2045
            examples:
            http://localhost:8080/static/dojo/img/zoom-in.cur - Failed to load resource: the server responded with a status of 404 (Not Found)
            http://localhost:8080/media/CACHE/images/finding_images/1bf9c0b1-5ed1-4b4e-9551-bcbfd198b90a/7d8d9af058566b8f2fe6548d96c63237.jpg - Failed to load resource: the server responded with a status of 404 (Not Found)

            The addition of the trigger exception is due to the Report Builder tests. All of the moving objects are from javascrip
            Tooltips are attached to each object and operate fine at human speeds. Selenium moves too fast for tooltips to be
            cleaned up, edited, and displayed, so the issue is only present in the test
            """
            accepted_javascript_messages = r"((zoom\-in\.cur.*)|(images\/finding_images\/.*)||(uploaded_files\/.*))404\ \(Not\ Found\)|Cannot read property \'trigger\' of null"
            # accepted_javascript_messages = r'((zoom\-in\.cur.*)|(images\/finding_images\/.*))404\ \(Not\ Found\)|(bootstrap\-chosen\.css\.map)'

            if entry["level"] == "SEVERE":
                # print(self.driver.current_url)  # TODO actually this seems to be the previous url
                # self.driver.save_screenshot("C:\\Data\\django-DefectDojo\\tests\\javascript-errors.png")
                # with open("C:\\Data\\django-DefectDojo\\tests\\javascript-errors.html", "w") as f:
                #    f.write(self.driver.page_source)

                print(entry)
                print(
                    "There was a SEVERE javascript error in the console, please check all steps fromt the current test to see where it happens"
                )
                print(
                    "Currently there is no reliable way to find out at which url the error happened, but it could be: ."
                    + self.driver.current_url
                )
                if self.accept_javascript_errors:
                    print(
                        "WARNING: skipping SEVERE javascript error because accept_javascript_errors is True!"
                    )
                elif re.search(accepted_javascript_messages, entry["message"]):
                    print(
                        "WARNING: skipping javascript errors related to finding images, see https://github.com/DefectDojo/django-DefectDojo/issues/2045"
                    )
                else:
                    self.assertNotEqual(entry["level"], "SEVERE")

        return True

    def tearDown(self):
        self.assertNoConsoleErrors()

        self.assertEqual([], self.verificationErrors)

    @classmethod
    def tearDownDriver(cls):
        print("tearDownDriver: ", cls.__name__)
        global dd_driver
        if dd_driver:
            if (
                not dd_driver_options.experimental_options
                or not dd_driver_options.experimental_options["detach"]
            ):
                print("closing browser")
                dd_driver.quit()


class WebdriverOnlyNewLogFacade(object):

    last_timestamp = 0

    def __init__(self, webdriver):
        self._webdriver = webdriver

    def get_log(self, log_type):
        last_timestamp = self.last_timestamp
        entries = self._webdriver.get_log(log_type)
        filtered = []

        for entry in entries:
            # check the logged timestamp against the
            # stored timestamp
            if entry["timestamp"] > self.last_timestamp:
                filtered.append(entry)

                # save the last timestamp only if newer
                # in this set of logs
                if entry["timestamp"] > last_timestamp:
                    last_timestamp = entry["timestamp"]

        # store the very last timestamp
        self.last_timestamp = last_timestamp

        return filtered
