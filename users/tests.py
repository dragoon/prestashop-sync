# -*- coding: utf-8 -*-

from django.core.urlresolvers import reverse
from django.core import mail
from django.test import TestCase
from django.utils.translation import ugettext as _
from django_selenium.livetestcases import SeleniumLiveTestCase
from users.models import Profile


class RegistrationTest(TestCase):

    def test_register_internal(self):

        # Get register page
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 405)

        # Register user
        form_data = {
            'email':'test@example.com',
            'password': 'test',
            'plan': Profile.PLAN_FREE
        }
        response = self.client.post(reverse('register'), form_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "success")

        # Test that one message has been sent.
        self.assertEqual(len(mail.outbox), 2)

        # Verify that the subject of the activation letter is correct.
        self.assertEqual(mail.outbox[1].subject, u"\u2713 " + _("Welcome to Prestashop-Sync Service"))
        self.assertEqual(mail.outbox[0].subject, "User registration")

        # Verify account created
        self.assertEqual(Profile.objects.filter(is_active=False).count(), 1)

        # Activate account
        activation_key = mail.outbox[1].body.split('confirm/')[1].strip().split()[0]
        response = self.client.get(reverse('confirm', args=[activation_key]), form_data)
        self.assertRedirects(response, '/')
        self.assertEqual(Profile.objects.filter(is_active=False).count(), 0)

    def test_business_register(self):
        """Test business plan register redirect"""

        # Register user
        form_data = {
            'email':'test@example.com',
            'password': 'test',
            'plan': Profile.PLAN_BUSINESS
        }
        response = self.client.post(reverse('register'), form_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "success")

        # Activate account and check business redirect
        activation_key = mail.outbox[1].body.split('confirm/')[1].strip().split()[0]
        response = self.client.get(reverse('confirm', args=[activation_key]), form_data)
        self.assertRedirects(response, reverse('payment'))
        self.assertEqual(Profile.objects.filter(is_active=False).count(), 0)


class InterfaceTest(SeleniumLiveTestCase):
    """Selenium functional tests"""
    fixtures = ('user_test_data',)

    def test_login(self):
        """Basic auth test"""
        self.driver.open_url(reverse('main'))
        self.driver.click('#authentication')
        self.driver.wait_for_visible('div.auth-form')
        self.driver.click('form#login_form input.link-button')

        # Check errors appear
        self.assertTrue(self.driver.wait_element_present('form#login_form #id_username + div.error'))
        self.assertTrue(self.driver.wait_element_present('form#login_form a.toggle-password + div.error'))

        self.driver.type_in('form#login_form #id_username', 'test@gmail.com')
        self.driver.click('form#login_form input.link-button')
        self.assertFalse(self.driver.is_element_present('form#login_form #id_username + div.error'))
        self.assertTrue(self.driver.is_element_present('form#login_form a.toggle-password + div.error'))
        # Login actual user
        self.driver.type_in('form#login_form #id_password', 'a')
        # Test show/hide password working
        self.driver.click('form#login_form a.toggle-password')
        self.assertTrue(self.driver.wait_for_visible('form#login_form input.password[type="text"]'))
        self.assertTrue(self.driver.wait_for_visible('form#login_form input.password[type="password"]', visible=False))
        self.driver.click('form#login_form a.toggle-password')
        self.assertTrue(self.driver.wait_for_visible('form#login_form input.password[type="password"]'))
        self.assertTrue(self.driver.wait_for_visible('form#login_form input.password[type="text"]', visible=False))

        self.driver.click('form#login_form input.link-button')
        # Check
        self.assertTrue(self.driver.is_element_present('#user_name_wrapper'))
        self.assertFalse(self.driver.is_element_present('#authentication'))
        # Log out
        self.driver.find('#user_name_wrapper a')[2].click()
        self.assertFalse(self.driver.is_element_present('#user_name_wrapper'))
        self.assertTrue(self.driver.is_element_present('#authentication'))

    def test_register(self):
        self.driver.open_url(reverse('main'))
        self.driver.click('#authentication')
        self.driver.wait_for_visible('div.auth-form')

        # go to options page
        self.driver.click('.login a')

        # open register dialog for free account
        self.driver.click('.pricingtable a')
        self.driver.click('form#register_form input.link-button')
        # Check errors appear
        #TODO: fix error
        #self.assertTrue(self.driver.wait_element_present('form#register_form #id_email + div.error'))
        self.assertTrue(self.driver.wait_element_present('form#register_form a.toggle-password + div.error'))
        # Register
        self.driver.type_in('form#register_form #id_email', 'test1@gmail.com')
        self.driver.type_in('form#register_form #id_password', 'MisterX')
        self.driver.click('form#register_form input.link-button')
        self.driver.wait_for_visible('#facebox')
        self.assertEquals(self.driver.find('#facebox div.content > div').text,
                          u'На ваш адрес было отправлено письмо с кодом активации аккаунта')
        Profile.objects.all().delete()
