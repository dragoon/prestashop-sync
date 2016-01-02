# -*- coding: utf-8 -*-

from StringIO import StringIO
from functools import wraps
import base64
import time
import os.path
import re

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils import simplejson
from django.utils.translation import ugettext as _
import unittest2
from presta.utils.presta_xml import get_xml_data
from tools.test_runner import InterfaceTestCase

SHOP_KEY = 'CH0EVLRYYY9X6MIX2J4ZTWHZ65UG8WVI'


def sync_type_loop(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        for sync_type in ('ID', 'EAN13'):
            print 'Testing {0}'.format(sync_type)
            func(self, sync_type, *args, **kwargs)
    return wrapper


def presta_version_loop(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        for presta_type in ('prestashop', 'prestashop15'):
            print 'Testing {0}'.format(presta_type)
            func(self, 'http://localhost:8080/%s' % presta_type, *args, **kwargs)
    return wrapper


def check_update_result(response, data):
    result_data = simplejson.loads(response.content)
    return re.search('''<input type="hidden" name="id" value="%(id)s">
                    <input type="hidden" name="id_attribute" value=%(id_attribute)s>
                    <input type="hidden" name="ean13" value=\\d+>
                    <input type="number" name="quantity" value="%(quantity)s">''' % data,
                     result_data['response'])


class PrestaAPIBaseTest(TestCase):
    fixtures = ('test_data',)

    def __init__(self, *args, **kwargs):
        super(PrestaAPIBaseTest, self).__init__(*args, **kwargs)
        base64string = base64.encodestring('%s:' % (SHOP_KEY,))[:-1]
        authheader = "Basic %s" % base64string
        self.headers = {"Authorization": authheader}

    def _get_xml_data(self, url):
        return get_xml_data(url, self.headers)

    def _update_and_check_ok(self, response, result='update_ok'):
        self.assertEquals(response.status_code, 200)
        result_data = simplejson.loads(response.content)
        self.assertEqual(result_data['result'], 'success')
        self.assertEqual(result_data['response'], result)

    def _set_csv_file(self, sync_type, quantity=30, price=100):
        if sync_type == 'EAN13':
            csv_file = StringIO('1000000000002,%d,%d' % (quantity, price))
        else:
            csv_file = StringIO('20,%d,%d' % (quantity, price))
        csv_file.name = 'prestashop.csv'
        return csv_file

    def _wait_for_update(self, data):
        result_data = {'result': None}
        for i in xrange(40):
            response = self.client.post(reverse('check_update'), data=data)
            self.assertEquals(response.status_code, 200)
            result_data = simplejson.loads(response.content)
            if result_data['result'] == 'success':
                break
            time.sleep(2)
        self.assertEqual(result_data['result'], 'success')


class PrestaAPITest(PrestaAPIBaseTest):

    @presta_version_loop
    @sync_type_loop
    def test_get_data(self, sync_type, domain):
        data = {'domain': domain,
                'sync_type': sync_type,
                'key':SHOP_KEY}
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed(response, 'partial/products_table.html')
        self.assertEqual(response.context['sync_type'], sync_type)

    @presta_version_loop
    def test_get_data_key_error(self, domain):
        data = {'domain': domain,
                'sync_type': 'ID',
                'key': 'WRONG'}
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)
        data = simplejson.loads(response.content)
        self.assertEqual(data['result'], 'error')

    @presta_version_loop
    def test_update_forbidden(self, domain):
        data = {'domain': domain,
                'sync_type': 'ID',
                'key': SHOP_KEY}
        self.assertTrue(self.client.login(email='user_a@example.com'))
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)

        # reduce syncs count to one
        from users.models import Profile
        user = Profile.objects.get(username='user_a@example.com')
        user.syncs_left = 1
        user.save()

        # perform update
        post_data = {'domain': domain, 'sync_type': 'ID', 'key': SHOP_KEY,
                     'id[]': '6', 'id_attribute[]': '0', 'ean13': '1000000000001',
                     'quantity[]': 250}
        response = self.client.post(reverse('update_data_single'), data=post_data)
        self._update_and_check_ok(response)

        # next time should be an error
        response = self.client.post(reverse('update_data_single'), data=post_data)
        self.assertEquals(response.status_code, 404)

    @presta_version_loop
    @sync_type_loop
    def test_update_data_single(self, sync_type, domain):
        data = {'domain': domain, 'sync_type': sync_type, 'key': SHOP_KEY,
                'id': '6', 'id_attribute': '0', 'ean13': '1000000000001',
                'quantity': 250}
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)

        post_data = {'domain': domain, 'sync_type': sync_type, 'key': SHOP_KEY,
                     'id[]': '6', 'id_attribute[]': '0', 'ean13': '1000000000001',
                     'quantity[]': 250}

        response = self.client.post(reverse('update_data_single'), data=post_data)
        self._update_and_check_ok(response)

        # Check updated values with get_data
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(check_update_result(response, data))

        # Update again and check
        post_data['quantity[]'] = data['quantity'] = 240
        response = self.client.post(reverse('update_data_single'), data=post_data)
        self.assertEquals(response.status_code, 200)
        response = self.client.post(reverse('get_data'), data=data)
        self.assertTrue(check_update_result(response, data))

    @presta_version_loop
    @sync_type_loop
    def test_update_data_single_combination(self, sync_type, domain):
        # TODO: check price does not change
        data = {'domain': domain, 'sync_type': sync_type, 'key': SHOP_KEY,
                'id': '2', 'id_attribute': '10', 'ean13': '1000000000002',
                'quantity': 40}
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)

        post_data = {'domain': domain, 'sync_type': sync_type, 'key': SHOP_KEY,
                     'id[]': '2', 'id_attribute[]': '10', 'ean13': '1000000000002',
                     'quantity[]': 40}
        if domain.endswith('15'):
            data['id_attribute'] = post_data['id_attribute[]'] = '4'
        response = self.client.post(reverse('update_data_single'), data=post_data)
        self._update_and_check_ok(response)

        # Check updated values with get_data
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(check_update_result(response, data))

        # Update again and check
        data['quantity'] = post_data['quantity[]'] = 30
        response = self.client.post(reverse('update_data_single'), data=post_data)
        self.assertEquals(response.status_code, 200)
        response = self.client.post(reverse('get_data'), data=data)
        self.assertTrue(check_update_result(response, data))

    @presta_version_loop
    @sync_type_loop
    def test_update_data(self, sync_type, domain):
        data_check1 = {'id': '2', 'id_attribute': '10', 'ean13': '1000000000002',
                       'quantity': 40}
        data_check2 = {'id': '6', 'id_attribute': '0', 'ean13': '1000000000001',
                       'quantity': 250}
        if domain.endswith('15'):
            data_check1['id_attribute'] = '4'
        if sync_type == 'EAN13':
            csv_file = StringIO('1000000000001,250\n1000000000002,40')
        else:
            csv_file = StringIO('25,250\n20,40')
            if domain.endswith('15'):
                csv_file = StringIO('30,250\n24,40')
        csv_file.name = 'prestashop.csv'
        data = {'domain': domain, 'sync_type': sync_type, 'key': SHOP_KEY,
                'csv_file': csv_file}
        response = self.client.post(reverse('update_data'), data=data)
        self._update_and_check_ok(response, 'ok')

        self._wait_for_update(data)

        # Check updated values with get_data
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(check_update_result(response, data_check1))
        self.assertTrue(check_update_result(response, data_check2))

        # Update again and check
        data_check1['quantity'] = 30
        data_check2['quantity'] = 240
        if sync_type=='EAN13':
            csv_file = StringIO('1000000000001,240\n1000000000002,30')
        else:
            csv_file = StringIO('25,240\n20,30')
            if domain.endswith('15'):
                csv_file = StringIO('30,240\n24,30')
        csv_file.name = 'prestashop.csv'
        data['csv_file'] = csv_file
        response = self.client.post(reverse('update_data'), data=data)
        self.assertEquals(response.status_code, 200)
        response = self.client.post(reverse('get_data'), data=data)
        self.assertTrue(check_update_result(response, data_check1))
        self.assertTrue(check_update_result(response, data_check2))

    @presta_version_loop
    @sync_type_loop
    def test_update_attributes(self, sync_type, domain):
        """Test price update"""
        csv_file = self._set_csv_file(sync_type)
        data = {'domain': domain, 'sync_type': sync_type, 'key': SHOP_KEY,
                'csv_file': csv_file}
        response = self.client.post(reverse('update_data'), data=data)
        # TODO: add check when we try to set already up-to date value
        # we tried to update already up-to-date data, check error
        #self.assertEqual(data['result'], 'error')
        # set another quantity
        #csv_file = self._set_csv_file(sync_type, quantity=31)

        self._update_and_check_ok(response, 'ok')
        self._wait_for_update(data)

        xml_data = self._get_xml_data("%s/api/combinations/10" % domain)
        self.assertEquals(float(xml_data.findtext('.//price')), 100.0)

        # Turn back to 0 price for attribute
        csv_file = self._set_csv_file(sync_type, price=0)
        data['csv_file'] = csv_file
        response = self.client.post(reverse('update_data'), data=data)
        self._update_and_check_ok(response, 'ok')
        self._wait_for_update(data)

        xml_data = self._get_xml_data("%s/api/combinations/10" % domain)
        self.assertEquals(float(xml_data.findtext('.//price')), 0)

    @presta_version_loop
    @sync_type_loop
    def test_save_csv(self, sync_type, domain):
        data = {'domain': domain,
                'sync_type': sync_type,
                'key': SHOP_KEY}
        response = self.client.post(reverse('get_data'), data=data)
        self.assertEquals(response.status_code, 200)
        response = self.client.get(reverse('save_csv'))
        self.assertEquals(response.status_code, 200)
        if sync_type == 'EAN13':
            self.assertContains(response, '1000000000001,240')
            self.assertContains(response, '1000000000002,30')
        else:
            self.assertContains(response, '25,240')
            self.assertContains(response, '20,30')


class PrestaAPI14Test(PrestaAPIBaseTest):

    def __init__(self, *args, **kwargs):
        super(PrestaAPI14Test, self).__init__(*args, **kwargs)
        self.domain = 'http://localhost:8080/prestashop'

    def test_add_products_csv(self):
        self.assertTrue(self.client.login(email='user_a@example.com'))
        csv_file = StringIO('test product,home,100,120,test description')
        csv_file.name = 'prestashop.csv'

        data = {'0': csv_file}

        response = self.client.post(reverse('upload_add_csv'), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['response'], _('File is valid'))
        self.assertEquals(result['lines'], 1)
        self.assertEquals(result['names'], ['test product'])

        # Attach image
        img_file = open(os.path.join(settings.STATICFILES_DIRS[0],
                                     'images', 'shop.jpg'), 'rb')
        data = {'0': img_file}
        response = self.client.post(reverse('add_images', args=[0]), data=data)
        img_file.close()
        result = simplejson.loads(response.content)
        self.assertEquals(result['response'], _("Drag images here."))

        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0'
        }

        response = self.client.post(reverse('add_data', args=[1]), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['result'], 'success')
        self.assertEquals(result['response'], '14_create_products')

        xml_data = self._get_xml_data("%s/api/products?display=[name,id]" % self.domain)

        name_elems = [elem for elem in xml_data.findall('.//language')
                      if elem.text == 'test product']
        self.assertTrue(name_elems)
        # Get product element
        product_id = name_elems[0].getparent().getparent().find('.//id').text
        xml_data = self._get_xml_data("%s/api/products/%s" % (self.domain, product_id))

        # Check product enabled
        self.assertEquals(xml_data.findtext('.//active'), '1')
        # Check image in images node
        self.assertTrue(xml_data.findtext('.//images/image/id'))
        # Check default image
        self.assertTrue(xml_data.findtext('.//id_default_image'))

    def test_add_products_form(self):
        self.assertTrue(self.client.login(email='user_a@example.com'))
        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-name': u'тестовый товар',
            'form-0-category': 1,
            'form-0-price': 100,
            'form-0-quantity': 100,
            'form-0-description': u'тест',
            'form-0-order': 0
        }
        response = self.client.post(reverse('add_data', args=[1]), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['result'], 'success')
        self.assertEquals(result['response'], '14_create_products')

        xml_data = self._get_xml_data("%s/api/products?display=[name,id]" % self.domain)
        name_elems = [elem for elem in xml_data.findall('.//language')
                      if elem.text == u'тестовый товар']
        self.assertTrue(name_elems)

        # Get product element
        product_id = name_elems[0].getparent().getparent().find('.//id').text
        xml_data = self._get_xml_data("%s/api/products/%s" % (self.domain, product_id))

        # Check product enabled
        self.assertEquals(xml_data.findtext('.//active'), '1')

    def test_add_products_error(self):
        self.assertTrue(self.client.login(email='user_a@example.com'))

        # Check error when submitting form with not enough fields
        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-name': u'тестовый товар',
            'form-0-category': 1,
            'form-0-price': 100,
            #'form-0-quantity': 100, - NO QUANTITY
            'form-0-description': u'тест',
            'form-0-order': 0
        }

        response = self.client.post(reverse('add_data', args=[1]), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['result'], 'error')
        self.assertEquals(result['response'], {'form-0-quantity': [_('This field is required.')]})

        # Check error when submitting form with CSV
        csv_file = StringIO('test product,home,ERROR,120,test description')
        csv_file.name = 'prestashop.csv'

        data = {'0': csv_file}

        self.client.post(reverse('upload_add_csv'), data=data)

        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0'
        }

        response = self.client.post(reverse('add_data', args=[1]), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['result'], 'success')
        self.assertEquals(result['response'], '14_update_permission_or_csv')


class PrestaTest(TestCase):

    def test_main_page(self):
        response = self.client.get(reverse('main'))
        self.assertEquals(response.status_code, 200)

    def test_upload_update_csv(self):
        """Upload csv file HTML5 drag drop"""

        # Valid
        csv_file = StringIO('25,240\n20,30')
        csv_file.name = 'prestashop.csv'
        data = {'0': csv_file}

        response = self.client.post(reverse('upload_update_csv'), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['response'], _('File is valid'))
        self.assertEquals(result['lines'], 2)

        # Not valid
        csv_file = StringIO('LOL! Invalid!')
        csv_file.name = 'prestashop.csv'
        data['0'] = csv_file
        response = self.client.post(reverse('upload_update_csv'), data=data)
        result = simplejson.loads(response.content)
        self.assertEquals(result['response'], _('File is not valid'))

    def test_delete_default_shop(self):
        """Regression Test"""
        self.client.get(reverse('main'))
        response = self.client.post(reverse('shop_delete', args=[1]))
        self.assertContains(response, 'ok')
        response = self.client.get(reverse('main'))
        self.assertEquals(response.status_code, 200)


class ShopActionTest(TestCase):

    @presta_version_loop
    def test_shop_CRUD(self, domain):
        # Add
        data = {'domain': domain, 'sync_type': 'ID', 'key': SHOP_KEY}
        response = self.client.post(reverse('add_shop'), data=data)
        result_data = simplejson.loads(response.content)
        self.assertEquals(result_data['result'], 'success')

        shop_id = result_data['response']
        # Read
        response = self.client.get(reverse('shop_status', args=[shop_id]))
        result_data = simplejson.loads(response.content)
        self.assertEquals(result_data[0], 'green')

        response = self.client.post(reverse('shop_status', args=[shop_id]))
        result_data = simplejson.loads(response.content)
        self.assertEquals(result_data[0], 'green')

        # Edit
        self.client.get(reverse('shop_edit', args=[shop_id]))

        # Delete
        response = self.client.post(reverse('shop_delete', args=[shop_id]))
        self.assertContains(response, 'ok')


class SyncLeftInterfaceTest(InterfaceTestCase):
    """Corner cases tests when running out of syncs"""
    fixtures = ('syncs_left',)

    def test_syncs_exhausted(self):
        # reduce syncs count to one
        self.driver.open_url(reverse('main'))
        self._login()

        # Test that demo-shop does not decrease syncs
        self.driver.click_and_wait('#load_data_demo', 'table.sync-data')
        self.driver.execute_script('$(".counter").removeClass("hidden")')
        self.assertEquals(self.driver.find('.exact-count').text, '2')
        self._single_update_and_restore()
        self.driver.execute_script('$(".counter").removeClass("hidden")')
        self.assertEquals(self.driver.find('.exact-count').text, '2')

        # Test another shop
        self.driver.click_and_wait('a.shop-load', 'table.sync-data')
        self.driver.find_elements_by_css_selector('#save_shop_question .link-button')[1].click()
        self._single_update_and_restore()

        self.assertEquals(self.driver.find('.exact-count').text, '0')

        self.driver.click('#update_data')
        self.assertEquals(self.driver.find('#facebox div.content > div').text,
                          u'Пожалуйста, перейдите на другой тариф чтобы продолжить')


class InterfaceTest(InterfaceTestCase):
    """Selenium functional tests"""

    def test_add_product_csv_clear(self):
        """
        Test that csv file for adding products is cleared when
        closing facebox dialog.
        """
        pass

    def test_sync_btn(self):
        """Click sync button - dialog should be loaded"""
        self.driver.open_url(reverse('main'))
        for auth_btn in ('#sync_btn', '#authentication'):
            self.driver.click(auth_btn)
            self.driver.wait_for_visible('div.auth-form')
            self.driver.click('#facebox a.close')
            self.driver.wait_for_visible('div.auth-form', visible=False)

    def test_switch_language(self):
        """Check language switching works"""
        self.driver.open_url(reverse('main'))
        self.driver.click_and_wait('#language_panel span.en', '#language_panel span.en.active')
        self.driver.click_and_wait('#language_panel span.ru', '#language_panel span.ru.active')

    def test_load_demo_single_update_data(self):
        """Check loading demo-data and perform single update"""
        # Load
        self.driver.open_url(reverse('main'))
        self.driver.click_and_wait('#load_data_demo', 'table.sync-data')
        self.assertTrue(self.driver.is_element_present('a.save-csv'))

        # Update
        self.assertEquals(self.driver.find('table.sync-data tbody tr input[name="id_attribute"]').get_attribute('value'), '25')
        self._single_update_and_restore()

        # save csv
        self.driver.click('a.save-csv')

    def test_load_data_shop_click(self):
        """test load data using click on the shop name"""
        self.driver.open_url(reverse('main'))
        self.driver.click_and_wait('a.shop-load', 'table.sync-data')
        self.assertTrue(self.driver.is_element_present('a.save-csv'))

    def test_pagination(self):
        """Test pagination"""

    def test_csv_update_data(self):
        """Check bulk data update"""
        self.driver.open_url(reverse('main'))
        open('test.csv', 'w').write('25,241\n20,31')
        self.driver.find('#id_csv_file').send_keys(os.path.join(os.getcwd(), 'test.csv'))
        self.driver.click('#update_data')
        # Check sync type was incorrect
        self.assertTrue(self.driver.wait_element_present('#load_data_form span.custom-select + div.error'))

        # set correct type
        self.driver.click('#load_data_form select#id_sync_type')
        self.driver.select('#load_data_form select#id_sync_type', "ID")
        self.driver.click('#update_data')
        # Check wait
        self.assertTrue(self.driver.wait_for_visible('#loading_dialog', visible=False))
        # check correct
        self.assertTrue(self.driver.wait_for_visible('#facebox'))
        self.assertEquals(self.driver.find('#facebox div.content > div').text,
                          u"Данные были успешно обновлены")
        self.driver.click('#facebox div.content > span.facebox-close')
        self.assertTrue(self.driver.wait_for_visible('#facebox', visible=False))

        # Restore old data
        open('test.csv', 'w').write('25,240\n20,30')
        self.driver.find('#id_csv_file').send_keys(os.path.join(os.getcwd(), 'test.csv'))
        self.driver.click('#update_data')
        self.assertTrue(self.driver.wait_for_visible('#loading_dialog', visible=False))
        self.assertTrue(self.driver.wait_for_visible('#facebox'))
        self.assertEquals(self.driver.find('#facebox div.content > div').text,
                          u"Данные были успешно обновлены")
        os.unlink('test.csv')

    def test_csv_dragdrop(self):
        """Test dropping file to drop zone"""
        self.driver.open_url(reverse('main'))
        open('test.csv', 'w').write('25,240\n20,30')
        self.driver.find('#id_csv_file').send_keys(os.path.join(os.getcwd(), 'test.csv'))
        self.driver.execute_script('fileList = Array();fileList.push($("#id_csv_file").get(0).files[0]);')
        self.driver.execute_script("e = $.Event('drop'); e.originalEvent = {dataTransfer : { files : fileList } }; $('#drop_zone').trigger(e);")
        self.assertTrue(self.driver.wait_element_present('#drop_zone.drop'))
        self.assertEquals(self.driver.find('#load_data_form div.file-list').text, 'test.csv')
        # check file upload persists
        self.driver.open_url(reverse('main'))
        self.assertEquals(self.driver.find('#load_data_form div.file-list').text, 'update_file.csv')
        # Delete upload
        self.driver.click('a.csv-action.delete')
        self.assertEquals(self.driver.find('#load_data_form div.file-list').text, '')
        # Check delete finished
        self.driver.open_url(reverse('main'))
        self.assertEquals(self.driver.find('#load_data_form div.file-list').text, '')
        os.unlink('test.csv')

    def test_add_products(self):
        """Test adding products"""
        self.driver.open_url(reverse('main'))
        self.driver.click('table.shop-table td.actions a.add')
        self.driver.wait_for_visible('#facebox .add-shop-products-form')

        self.driver.type_in('.add-shop-products-form #id_form-0-name', 'Test product')
        self.driver.type_in('.add-shop-products-form #id_form-0-price', '100')
        self.driver.type_in('.add-shop-products-form #id_form-0-quantity', '100')
        self.driver.type_in('.add-shop-products-form #id_form-0-description', 'test description')

        self.driver.click('.add-shop-products-form input.link-button')
        self.assertTrue(self.driver.wait_element_present('.add-shop-products-form', present=False))
        # Check wait
        self.assertTrue(self.driver.wait_for_visible('#loading_dialog', visible=False))
        # check correct
        self.assertTrue(self.driver.wait_for_visible('#facebox'))
        self.assertEquals(self.driver.find('#facebox div.content > div').text,
                          u"Товары добавлены в магазин. Загрузка картинок может потребовать нескольких минут.")
        self.driver.click('#facebox div.content > span.facebox-close')
        self.assertTrue(self.driver.wait_for_visible('#facebox', visible=False))
        self.driver.click_and_wait('#load_data_demo', 'table.sync-data')
        self.assertEquals(self.driver.find_elements_by_css_selector('table.sync-data tr')[-1].find_elements_by_css_selector('td')[2].text,
                          "Test product")

    def test_add_products_images(self):
        """Test adding products with images"""

    def test_add_products_csv(self):
        """Test adding products with csv file"""
        self.driver.open_url(reverse('main'))
        # First try incorrect file
        self.driver.click('table.shop-table td.actions a.add')
        self.driver.wait_for_visible('#facebox .add-shop-products-form')
        self.driver.drop_image('presta/fixtures/add_products_err.csv', '#add_products_csv',
                               '#facebox')
        # Check file is incorrect
        self.assertTrue(self.driver.wait_element_present('#add_products_csv.drop-error'))

        # Attach new file
        self.driver.drop_image('presta/fixtures/add_products.csv', '#add_products_csv', '#facebox')

        # add images
        self.driver.drop_image('static/images/transparent.png', '.add-shop-products-form .product-image-upload', '#facebox')
        self.driver.click('.add-shop-products-form .submit-wrapper input.link-button')
        self.assertTrue(self.driver.wait_element_present('.add-shop-products-form', present=False))
        # Check wait
        self.assertTrue(self.driver.wait_for_visible('#loading_dialog', visible=False))
        # check correct
        self.assertTrue(self.driver.wait_for_visible('#facebox'))
        self.assertEquals(self.driver.find('#facebox div.content > div').text,
                          u"Товары добавлены в магазин. Загрузка картинок может потребовать нескольких минут.")
        self.driver.click('#facebox div.content > span.facebox-close')
        self.assertTrue(self.driver.wait_for_visible('#facebox', visible=False))

    def test_shop_edit(self):
        """Test shop edit and save"""
        self.driver.open_url(reverse('main'))
        # Edit link click
        self.driver.click('table.shop-table td.actions a.edit')
        self.driver.wait_for_visible('#facebox #switch')

        # Activate scheduled updates
        self.assertTrue(self.driver.is_element_present('#facebox #id_location[disabled]'))
        self.driver.click('#facebox #switch')
        self.driver.click('#facebox input.link-button')
        self.driver.wait_for_visible('#facebox', visible=False)

        self.driver.click('table.shop-table td.actions a.edit')
        self.assertFalse(self.driver.is_element_present('#facebox #id_location[disabled]'))

    def test_shop_add(self):
        """Test shop adding"""
        self.driver.open_url(reverse('main'))
        self._login()
        self.driver.click('#add_shop a')
        self.driver.wait_for_visible('#facebox')
        # TODO: test wrong data

        # Fill the form with correct data
        self.driver.type_in('#facebox #id_domain', 'http://localhost:8080/prestashop')
        self.driver.type_in('#facebox #id_key', SHOP_KEY)
        self.driver.click('#facebox input.link-button')
        self.assertTrue(self.driver.wait_for_visible('#loading_dialog', visible=False))
        self.assertTrue(self.driver.wait_element_present('tr#shop_2 td.status a.green'))

    def test_shop_delete(self):
        """Test shop deleting"""
        self.driver.open_url(reverse('main'))
        self.driver.click('table.shop-table td.actions a.delete')
        self.driver.wait_for_visible('#facebox')
        self.driver.click('#facebox a#delete_shop')
        self.assertFalse(self.driver.is_element_present('table.shop-table tbody tr'))


class SimpleTest(unittest2.TestCase):
    """Tests to see if basic functions work"""
    def test_make_data_list(self):
        from presta.utils.presta_api import make_data_list
        # Test already existing values
        lines = [('1', {'quantity': '51'})]
        data = [('1', '25', '25', 'iPod Nano', 'Blue, 16Go', {'price': '41.806020', 'quantity': '51'})]
        sync_type = 'ID'
        res = make_data_list(data, sync_type, lines)
        self.assertEquals(res['result'], 'success')
        self.assertEquals(res['response'], [])

        # Test new values
        lines = [('1', {'quantity': '52'})]
        res = make_data_list(data, sync_type, lines)
        self.assertEquals(res['result'], 'success')
        self.assertEquals(res['response'], [('1', '25', {'quantity': '52'})])

        # Test error
        lines = []
        res = make_data_list(data, sync_type, lines)
        self.assertEquals(res['result'], 'error')
        self.assertEquals(res['response'].keys()[0], 'sync_type')
