import unittest
from django.db.models.loading import get_app, get_apps
from django.test.simple import build_test, build_suite, reorder_suite
from django.conf import settings
from django.utils.unittest.case import TestCase

from django_coverage.coverage_runner import CoverageRunner
from django_selenium.livetestcases import SeleniumLiveTestCase

class MyTestSuiteRunner(CoverageRunner):
    """Overwrites standard runner to disable django tests"""

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        suite = unittest.TestSuite()

        if test_labels:
            for label in test_labels:
                if '.' in label:
                    suite.addTest(build_test(label))
                else:
                    app = get_app(label)
                    suite.addTest(build_suite(app))
        else:
            for app in get_apps():
                if app.__name__.startswith('django.'):
                    continue # disable django built-in tests
                suite.addTest(build_suite(app))

        if extra_tests:
            for test in extra_tests:
                suite.addTest(test)

        return reorder_suite(suite, (TestCase,))

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        setattr(settings, 'CELERY_ALWAYS_EAGER', True)
        super(MyTestSuiteRunner, self).run_tests(test_labels, extra_tests, **kwargs)


class InterfaceTestCase(SeleniumLiveTestCase):
    """Default interface test case to provide common methods"""

    def _login(self, email='test@gmail.com', password='a'):
        """Login user to the system"""
        self.driver.click('#authentication')
        self.driver.wait_for_visible('div.auth-form')
        # Type in username and password
        self.driver.type_in('form#login_form #id_username', email)
        self.driver.type_in('form#login_form #id_password', password)
        self.driver.click('form#login_form input.link-button')
        # Check
        self.assertTrue(self.driver.is_element_present('#user_name_wrapper'))
        self.assertFalse(self.driver.is_element_present('#authentication'))

    def _single_update_and_restore(self):
        """Performs quantity update for the product in the first row"""
        import time
        old_q = self.driver.find('table.sync-data tbody tr input[name="quantity"]').get_attribute('value')
        new_q = int(old_q) + 1
        time.sleep(1)
        self.driver.click('table.sync-data tbody tr input[name="quantity"]')
        self.driver.type_in('table.sync-data tbody tr input[name="quantity"]', new_q)
        self.assertFalse(self.driver.is_element_present('.btn.update.disabled'))
        self.driver.click('.btn.update')
        self.assertTrue(self.driver.wait_element_present('.btn.update.disabled'))
        self.driver.type_in('table.sync-data tbody tr input[name="quantity"]', old_q)
        self.driver.click('table.sync-data tbody tr input[name="quantity"]')
        self.driver.click('.btn.update')
        self.assertTrue(self.driver.wait_element_present('.btn.update.disabled'))
