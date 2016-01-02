from collections import defaultdict
from datetime import datetime
from httplib import HTTPException
import re
import urllib
import urllib2
import socket

from celery.task import task
from django.template.loader import render_to_string
from django.test.client import MULTIPART_CONTENT, encode_multipart, BOUNDARY
from django.utils.encoding import smart_str
from django.utils.translation import ugettext as _
from presta.forms import UpdateProductValidator

from presta.utils.presta_xml import get_xml_data, clean_chunked_data
from tools.errors import PrestaError
from tools.retry import retry
from tools.utils import send_email, print_timing

myopener = urllib2.build_opener()
myopener.addheaders = [('User-agent', 'Test Agent'), ('Cache-Control', 'no-cache,max-age=0'),
                       ('Pragma', 'no-cache')]

JOINED_ATTRS = ','.join(zip(*UpdateProductValidator.ATTRS)[0])


def build_id_list(data_dict):
    """Builds list of tuples suitable to pass to template.
       Lists are different for different sync_type"""
    # TODO: move to models and make private

    result = []

    # Parse products that have combinations
    for id_product, sync_type, values in data_dict['product']:
        product_name = data_dict['product_lang'][id_product]
        if data_dict['product_attribute'] and id_product in data_dict['product_attribute']:
            # also append product, but remove quantity from values
            values_copy = values.copy()
            values_copy['combination'] = True
            del values_copy['quantity']
            result.append((id_product, '0', sync_type, product_name, '', values_copy))
            for id_product_attribute, sync_type, values in data_dict['product_attribute'][id_product]:
                id_attributes = data_dict['product_attribute_combination'][id_product_attribute]
                attribute_names = ', '.join(sorted([data_dict['attribute_lang'][id] for id in id_attributes], reverse=True))
                result.append((id_product, id_product_attribute, sync_type, product_name, attribute_names, values))
        else:
            result.append((id_product, '0', sync_type, product_name, '', values))
    return result


def make_data_list(data, sync_type, lines):
    """
    Generates update data list suitable to supply to update api function
    """
    valid = False
    data_list = []
    data_dict = {}
    if sync_type != 'ID':
        # 2 is the index of the sync type attribute, and row is the values dict
        data_dict = dict([(row[2], row) for row in data])
    # try to split values in row
    # and populate result array
    for k, values_dict in lines:
        # File is already checked when we are here
        if sync_type == 'ID':
            k = int(k) - 1
            try:
                old_values = data[k][5]
                if not set(old_values.iteritems()).issuperset(set(values_dict.iteritems())):
                    data_list.append((data[k][0], data[k][1], values_dict))
                valid = True
            except IndexError:
                pass
        else:
            # if sync_type is NOT ID then k == UNIQ_SYNC_ATTR
            # Check if EAN exists
            if k in data_dict:
                old_values = data_dict[k][5]
                if 'combination' in old_values:
                # Main product with combinations, need to update only price
                    del values_dict['quantity']
                if not set(old_values.iteritems()).issuperset(set(values_dict.iteritems())):
                    id, id_attribute = data_dict[k][:2]
                    data_list.append((id, id_attribute, values_dict))
                valid = True
    if not valid:
        # If data_list is empty at the end then
        # probably sync_type was incorrect
        return {'result': 'error', 'response': {'sync_type': _('Incorrect value')}}
    return {'response': data_list, 'result': 'success'}


class PrestashopAPI:

    def __init__(self, shop):
        self.shop = shop
        self.finished = False

    @classmethod
    @retry(urllib2.URLError)
    def urlopen(cls, *args, **kwargs):
        urllib2.urlopen(*args, **kwargs)

    @classmethod
    def getAPI(cls, shop):
        """
        :type shop: Shop
        :rtype: PrestashopAPI
        """
        try:
            PrestashopAPI.urlopen(u'http://{0}/api'.format(shop.domain).encode('utf-8'), timeout=5)
        except urllib2.HTTPError, e:
            status = e.code
            if status in (401,403):
                headers = {"Authorization": shop.authheader}
                try:
                    data = get_xml_data(u'http://{0}/api/'.format(shop.domain).encode('utf-8'), headers)
                    if data.findtext('.//stock_availables/description'):
                        return PrestashopAPI15(shop)
                except urllib2.HTTPError:
                    pass
                except urllib2.URLError:
                    shop.set_alarm('URL is not valid')
                return PrestashopAPI14(shop)
        except (urllib2.URLError, socket.timeout):
            # TODO: set different alarm for timeout
            shop.set_alarm('URL is not valid')
        return PrestashopAPI14(shop)

    @print_timing
    def get_presta_data(self, page_num, page_limit):
        domain = self.shop.domain
        headers = {"Authorization": self.shop.authheader}
        sync_type = self.shop.sync_type.lower()
        result_dict = {}

        try:
            # get products
            initial_index = page_num * page_limit
            data = get_xml_data("http://%s/api/%s?display=[id,%s,%s,name]&sort=[id_ASC]&limit=%d,%d&price[base_price][use_reduction]=0&price[base_price][use_tax]=0"
                                % (domain, 'products', sync_type, JOINED_ATTRS, initial_index, page_limit), headers)

            self._get_presta_data(headers, data, result_dict, domain, sync_type, page_limit, page_num)
        except urllib2.HTTPError as e:
            error = PrestaError.get_error(PrestaError.DOMAIN, 'Incorrect value', self)
            if e.code == 500:
                # This should never happen after we implemented proper pagination
                message = e.fp.read()
                send_email.delay('mail/error', {'domain': domain, 'data_list': str(e.message),
                                                'full_data': str(page_num), 'message': str(message)},
                                 "Client Error")
                error = {PrestaError.DOMAIN: _('You have some problem with API access configuration,<br>'
                                               'try if API works by manually examining url:<br>') +
                                             '<a href="http://%s/api/products">http://%s/api/products</a>' % (domain, domain)}
            elif e.code in (401, 403):
                # send email about this
                send_email.delay('mail/error', {'domain': domain, 'data_list': '',
                                                'full_data': '', 'message': ''}, "Incorrect key")
                error = PrestaError.get_error(PrestaError.KEY, 'Incorrect value', self)
                if 'attribute_lang' in result_dict:
                    error = PrestaError.get_error(PrestaError.KEY, PrestaError.PROD_COMBINATIONS, self)
                elif 'product' in result_dict:
                    error = PrestaError.get_error(PrestaError.KEY, PrestaError.PROD_OPTIONS_VALUES, self)
            elif e.code == 404 or e.code == 503:
                error = PrestaError.get_error(PrestaError.DOMAIN, PrestaError.NOT_ACTIVATED, self)
            return result_dict, error
        except (urllib2.URLError, socket.timeout):
            # either timeout or dns error
            error = PrestaError.get_error(PrestaError.DOMAIN, PrestaError.NOT_REACHABLE, self)
            return result_dict, error
        except PrestaError, e:
            # no products found in the shop
            error = PrestaError.get_error(PrestaError.DOMAIN, e.message, self)
            return result_dict, error

        return result_dict, None

    def _get_presta_data(self, headers, data, result_dict, domain, sync_type, page_limit, page_num):
        """Stub for overriding"""


class PrestashopAPI14(PrestashopAPI):
    __version__ = '1.4'

    @property
    def default_lang(self):
        if hasattr(self, '_default_lang'):
            return self._default_lang
        domain = self.shop.domain
        headers = {"Authorization": self.shop.authheader}
        # get default language
        try:
            data = get_xml_data("http://%s/api/%s/1" % (domain, 'configurations'), headers)
            id_lang = data.findtext('.//value')
            if not id_lang:
                id_lang = '1'
        except urllib2.URLError:
            id_lang = '1'
        self._default_lang = id_lang
        return id_lang

    def get_categories(self):
        domain = self.shop.domain
        categories = []
        headers = {"Authorization": self.shop.authheader}
        try:
            data = get_xml_data("http://%s/api/%s?display=[id,name]" % (domain, 'categories'), headers)
        except urllib2.URLError:
            # return non-empty list to prevent IndexErrors
            return [('1', _('NO CATEGORIES FOUND'))]
        for c in data.findall('.//category'):
            id = c.findtext('.//id')
            name = c.findtext(".//language[@id='%s']" % self.default_lang)
            categories.append((id, name))
        if not categories:
            # return non-empty list to prevent IndexErrors
            categories = [('1', _('NO CATEGORIES FOUND'))]
        return categories

    def _get_presta_data(self, headers, data, result_dict, domain, sync_type, page_limit, page_num):

        id_lang = self.default_lang

        result_dict['product'] = []
        result_dict['product_lang'] = {}
        for elem in data.findall('.//product'):
            values_dict = {}
            for attr, formatter in UpdateProductValidator.ATTRS:
                values_dict[attr] = formatter(elem.findtext('.//%s' % attr))
            result_dict['product'].append((elem.findtext('.//id'),
                                           elem.findtext('.//%s' % sync_type), values_dict))

        for elem in data.findall('.//product'):
            id = elem.findtext('.//id')
            result_dict['product_lang'][id] = elem.findtext(".//language[@id='%s']" % id_lang)
            if not result_dict['product_lang'].get(id):
                try:
                    result_dict['product_lang'][id] = elem.findall('.//language')[0].text
                except KeyError:
                    result_dict['product_lang'][id] = _('DUMMY')

        # product ids are later used to select combinations
        product_ids = '|'.join(result_dict['product_lang'].keys())
        # Finished is set to True so we can exit the loop
        if len(result_dict['product_lang'].keys()) < page_limit:
            self.finished = True
        else:
            self.finished = False

        # get attributes
        data = get_xml_data("http://%s/api/%s?display=[id,name]" % (domain, 'product_option_values'), headers)
        result_dict['attribute_lang'] = {}
        for elem in data.findall('.//product_option_value'):
            id = elem.findtext('.//id')
            result_dict['attribute_lang'][id] = elem.findtext(".//language[@id='%s']" % id_lang)
            if not result_dict['attribute_lang'].get(id):
                try:
                    result_dict['attribute_lang'][id] = elem.findall('.//language')[0].text
                except KeyError:
                    result_dict['attribute_lang'][id] = _('DUMMY')

        # get combinations
        data = get_xml_data("http://%s/api/%s?display=full&sort=[id_ASC]&filter[id_product]=[%s]"
                            % (domain, 'combinations', product_ids), headers)
        result_dict['product_attribute'] = defaultdict(list)
        result_dict['product_attribute_combination'] = {}
        for elem in data.findall('.//combination'):
            comb_id = elem.findtext('.//id')
            values_dict = {}
            for attr, formatter in UpdateProductValidator.ATTRS:
                values_dict[attr] = formatter(elem.findtext('.//%s' % attr))
            result_dict['product_attribute'][elem.findtext('.//id_product')].append(
                (comb_id, elem.findtext('.//%s' % sync_type), values_dict))

            result_dict['product_attribute_combination'][comb_id] = []
            for elem in elem.findall('.//product_option_value'):
                # Check if id is indeed in attributes, it can happen if DB is corrupted.
                attr_id = elem.findtext('.//id')
                if attr_id in result_dict['attribute_lang']:
                    result_dict['product_attribute_combination'][comb_id].append(attr_id)

    def update_presta_data(self, data_list):
        """data_list = """
        domain = self.shop.domain
        authheader = self.shop.authheader
        total_results = {'errors': []}

        total = 0
        for row in data_list:
            id = row[0]
            id_attribute = row[1]
            is_combination = bool(id_attribute != '0')

            if is_combination:
                resource = 'combinations/' + str(id_attribute)
            else:
                resource = 'products/' + str(id)

            req = urllib2.Request("http://%s/api/%s?price[base_price][use_reduction]=0&price[base_price][use_tax]=0" % (domain, resource),
                                  headers={'Content-Type': 'text/xml',
                                           'Authorization': authheader})
            try:
                xml = urllib2.urlopen(req).read()
            except urllib2.HTTPError as e:
                err_msg = e.fp.read()
                total_results['errors'].append({'message': str(e), 'details': err_msg,
                                                'product': id, 'combination': int(id_attribute)})
                continue

            xml = clean_chunked_data(xml)
            xml = xml.decode('utf-8')
            # replace base_price with price for combinations
            if is_combination:
                price = re.findall(ur'<price>(.*)</price>', xml)[0]
                xml = re.sub(ur'(?<=<base_price>)(.*)(?=</base_price>)', price, xml)

            for attr_name, attr_value in row[2].items():
                xml = re.sub(ur'<{0}>(.*)</{0}>'.format(attr_name),
                             u'<{0}>{1}</{0}>'.format(attr_name, attr_value), xml)
            # remove non-settable fields
            xml = re.sub(r'<id_default_image(.+)</id_default_image>', '', xml)
            xml = re.sub(r'<position_in_category(.+)</position_in_category>', '', xml)
            xml = re.sub(r'<manufacturer_name(.+)</manufacturer_name>', '', xml)
            xml = re.sub(r'<associations>(.+)</associations>(?s)', '', xml)
            # replace price with base_price
            base_price = re.findall(ur'<base_price>(.*)</base_price>', xml)[0]
            xml = re.sub(ur'(?<=<price>)(.*)(?=</price>)', base_price, xml)
            # replace empty price
            xml = xml.replace(u'<price></price>', u'<price>0</price>')

            req = urllib2.Request(str("http://%s/api/%s" % (domain, resource)),
                                  headers={'Content-Type': 'application/x-www-form-urlencoded',
                                           'Authorization': authheader})
            req.get_method = lambda: 'PUT'

            try:
                urllib2.urlopen(req, data=xml.encode('utf-8'))
                total += 1
            except urllib2.HTTPError as e:
                err_msg = e.fp.read()
                total_results['errors'].append({'message': str(e), 'details': err_msg,
                                                'product': id, 'combination': int(id_attribute)})
            except HTTPException as e:
                total_results['errors'].append({'message': str(e), 'details': e.message,
                                                'product': id, 'combination': int(id_attribute)})

        if total:
            total_results['result'] = 'update_ok'
        else:
            total_results['result'] = '14_update_permission'
        total_results['count'] = total
        return total_results

    def add_product_data(self, data_list, images):
        """
        :param data_list: list of product data in the following form:
        [{'ean13':EAN13, 'price':PRICE, 'categories':[MAIN_CATEGORY, OTHER,...],
          'langs': ['id':LANG_ID, 'name':PRODUCT_NAME, 'link_rewrite': link_rewrite]},...]
        see how these fields are generated in AddProductsShopForm.clean() method.
        :param images: list of images for every product
        :return: update_ok string if everything is fine, error string that matches
                 HTML ID in template otherwise
        """

        # Check default lang, add link rewrite if it is different
        default_lang = self.default_lang
        for prod in data_list:
            langs = set([lang['id'] for lang in prod['langs']])
            if default_lang not in langs:
                new_value = prod['langs'][0].copy()
                new_value['id'] = default_lang
                prod['langs'].append(new_value)

        domain = self.shop.domain
        headers = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Authorization': self.shop.authheader}

        context = {'prestashop_url': domain, 'products': data_list,
                   'date_add': datetime.now()}

        products_xml = render_to_string('xml_templates/add_products.xml', context).encode('utf-8')

        try:
            result = get_xml_data("http://%s/api/products" % domain,
                                  headers, urllib.urlencode({'xml': products_xml}))
            # Extract product ids
            product_ids = [e.text for e in result.findall('.//product/id')]

            # IMAGES ADD CODE
            self.add_images.delay(self, product_ids, images)

        except urllib2.HTTPError, e:
            result = e.fp.read()
            send_email.delay('mail/error', {'domain': domain, 'message': str(result),
                                            'data_list': str(data_list),
                                            'full_data': ''}, "Add product client Error")
            return '14_update_permission_or_csv'
        return "14_create_products"

    @task(ignore_result=True)
    def add_images(self, product_ids, images):
        domain = self.shop.domain
        headers = {'Content-Type': MULTIPART_CONTENT,
                   'Authorization': self.shop.authheader}
        for i, p_images in enumerate(images):
            # TODO: why sometimes index does not exist?
            if i >= len(product_ids):
                send_email.delay('mail/error', {'domain': domain, 'message': str(product_ids),
                                                'data_list': '',
                                                'full_data': ''}, "Add images error")
                break
            product_id = product_ids[i]
            for image in p_images:
                data = encode_multipart(BOUNDARY, {'image': image})
                req = urllib2.Request(smart_str("http://%s/api/images/products/%s" % (domain, product_id)),
                                      headers=headers, data=smart_str(data))
                urllib2.urlopen(req)
        self.make_first_image_default(product_ids, headers)

    def make_first_image_default(self, product_ids, headers):
        if self.__version__ == PrestashopAPI15.__version__:
            return
        del headers['Content-Type']
        domain = self.shop.domain
        data_list = []
        context = {'prestashop_url': domain, 'products': data_list}

        for product_id in product_ids:
            prod_dict = {'id': product_id}
            data = get_xml_data("http://%s/api/products/%s" % (domain, product_id), headers)
            prod_dict['out_of_stock'] = data.findtext('.//out_of_stock')
            prod_dict['price'] = data.findtext('.//price')
            prod_dict['quantity'] = data.findtext('.//quantity')
            prod_dict['image_id'] = data.findtext('.//images/image/id')
            data_list.append(prod_dict)

        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        xml = render_to_string('xml_templates/update_products.xml', context)
        req = urllib2.Request(smart_str("http://%s/api/products" % (domain,)),
                              headers=headers)
        req.get_method = lambda: 'PUT'
        urllib2.urlopen(req, data=xml.encode('utf-8'))


class PrestashopAPI15(PrestashopAPI14):
    __version__ = '1.5'

    @print_timing
    def _get_presta_data(self, headers, data, result_dict, domain, sync_type, page_limit, page_num):

        id_lang = self.default_lang

        presta_version = get_xml_data("http://%s/api/%s?display=[name,value]"
                                      % (domain, 'configurations'), headers)
        presta_db_version = ''
        sort_attr = '&sort=[id_ASC]'
        for attr in presta_version.findall('.//configuration'):
            attr_name = attr.findtext('.//name')
            if attr_name == 'PS_VERSION_DB':
                presta_db_version = attr.findtext('.//value')
                break

        if presta_db_version == '1.5.5.0':
            sort_attr = ''

        # get products
        initial_index = page_num * page_limit
        data = get_xml_data("http://%s/api/%s?display=[id,%s,%s,name]%s&limit=%d,%d&price[base_price][use_reduction]=0&price[base_price][use_tax]=0"
                            % (domain, 'products', sync_type, JOINED_ATTRS, sort_attr, initial_index, page_limit), headers)

        result_dict['product'] = {}
        result_dict['product_lang'] = {}
        for elem in data.findall('.//product'):
            product_id = elem.findtext('.//id')
            values_dict = {}
            for attr, formatter in UpdateProductValidator.ATTRS:
                attr_value = elem.findtext('.//%s' % attr)
                # TODO: report it
                if not attr_value:
                    attr_value = '0'
                values_dict[attr] = formatter(attr_value)
            result_dict['product'][product_id] = {'sync_type': elem.findtext('.//%s' % sync_type),
                                                  'values': values_dict}
            product_name = elem.findtext(".//language[@id='%s']" % id_lang)
            if not product_name:
                try:
                    product_name = elem.findall('.//language')[0].text
                except KeyError:
                    product_name = _('DUMMY')
            result_dict['product_lang'][product_id] = product_name

        # product ids are later used to select combinations
        product_ids = sorted([int(k) for k in result_dict['product_lang'].keys()])

        # if there are no products - ha, didn't expect someone doing this
        if not product_ids:
            raise PrestaError(PrestaError.NO_PRODUCTS)

        max_prod_id = max(product_ids)
        min_prod_id = min(product_ids)
        product_ids = str(min_prod_id) + ',' + str(max_prod_id)
        # Finished is set to True so we can exit the loop
        if len(result_dict['product_lang'].keys()) < page_limit:
            self.finished = True
        else:
            self.finished = False

        # get attributes
        data = get_xml_data("http://%s/api/%s?display=[id,name]" % (domain, 'product_option_values'), headers)
        result_dict['attribute_lang'] = {}
        for elem in data.findall('.//product_option_value'):
            id = elem.findtext('.//id')
            result_dict['attribute_lang'][id] = elem.findtext(".//language[@id='%s']" % id_lang)
            if not result_dict['attribute_lang'].get(id):
                try:
                    result_dict['attribute_lang'][id] = elem.findall('.//language')[0].text
                except KeyError:
                    result_dict['attribute_lang'][id] = _('DUMMY')

        # get combinations
        data = get_xml_data("http://%s/api/%s?display=full&sort=[id_product_ASC]&filter[id_product]=[%s]"
                            % (domain, 'combinations', product_ids), headers)
        result_dict['product_attribute'] = defaultdict(dict)
        result_dict['product_attribute_combination'] = {}
        for elem in data.findall('.//combination'):
            comb_id = elem.findtext('.//id')
            prod_id = elem.findtext('.//id_product')
            # TODO: skip prod_ids that are not present in the 'product' dict
            # TODO: happens because of prestashop sorting BUG
            if not prod_id in result_dict['product']:
                continue
            values_dict = {}
            for attr, formatter in UpdateProductValidator.ATTRS:
                # TODO: hack because we don't have base_price
                if attr == 'base_price':
                    values_dict[attr] = formatter(elem.findtext('.//%s' % 'price'))
                else:
                    values_dict[attr] = formatter(elem.findtext('.//%s' % attr))
            result_dict['product_attribute'][prod_id][comb_id] =\
            {'sync_type': elem.findtext('.//%s' % sync_type), 'values': values_dict}
            result_dict['product_attribute_combination'][comb_id] = [elem.findtext('.//id') for elem in elem.findall('.//product_option_value')]

        # get stock_data
        data = get_xml_data("http://%s/api/%s?display=[id_product,id_product_attribute,quantity]&sort=[id_product_ASC]&filter[id_product]=[%s]"
                            % (domain, 'stock_availables', product_ids), headers)
        for elem in data.findall('.//stock_available'):
            prod_id = elem.findtext('.//id_product')
            comb_id = elem.findtext('.//id_product_attribute')
            quantity = elem.findtext('.//quantity')
            # TODO: log?
            # sometimes prod_id is empty - this is weird but we need to handle it
            if prod_id:
                # TODO: check why prod_id does not exist, may be convert to dict from defaultdict
                if comb_id != '0' and prod_id in result_dict['product_attribute']:
                    # Weird situation again we should check whether comb_id present,
                    # sometimes it's not. TODO: log?
                    try:
                        result_dict['product_attribute'][prod_id][comb_id]['values']['quantity'] = quantity
                    except KeyError:
                        pass
                else:
                    # TODO: skip prod_ids that are not present in the 'product' dict
                    # TODO: happens because of sorting bug
                    if prod_id in result_dict['product']:
                        result_dict['product'][prod_id]['values']['quantity'] = quantity

        # change values format back:
        products = []
        for prod_id, values in result_dict['product'].iteritems():
            products.append((prod_id, values['sync_type'], values['values']))
        result_dict['product'] = products

        product_attributes = defaultdict(list)
        for prod_id, values in result_dict['product_attribute'].iteritems():
            for comb_id, values in values.items():
                product_attributes[prod_id].append((comb_id, values['sync_type'], values['values']))
            products.append((prod_id, values['sync_type'], values['values']))
        result_dict['product_attribute'] = product_attributes

    def update_presta_data(self, data_list):
        """data_list = """
        domain = self.shop.domain
        authheader = self.shop.authheader
        headers = {"Authorization": self.shop.authheader}
        total_results = {'errors': []}

        # count how many products were updated
        total_price = 0
        total_count = 0
        # set to true if we find products that depend on stock
        depends_on_stock = False

        for row in data_list:
            id = row[0]
            id_attribute = row[1]
            is_combination = bool(id_attribute != '0')

            # PRICE update goes first -----------------
            if is_combination:
                resource = 'combinations/' + str(id_attribute)
            else:
                resource = 'products/' + str(id)

            if 'base_price' in row[2]:
                try:
                    # TODO: we're always replacing the price here, so we don't actually need it, but keep it for consistency with 1.4
                    req = urllib2.Request("http://%s/api/%s?price[base_price][use_reduction]=0&price[base_price][use_tax]=0" % (domain, resource),
                                          headers={'Content-Type': 'text/xml',
                                                   'Authorization': authheader})
                    xml = urllib2.urlopen(req).read()
                    xml = clean_chunked_data(xml)
                    xml = xml.decode('utf-8')

                    # replace base_price with price for combinations
                    if is_combination:
                        price = re.findall(ur'<price>(.*)</price>', xml)[0]
                        xml = re.sub(ur'(?<=<base_price>)(.*)(?=</base_price>)', price, xml)

                    for attr_name, attr_value in row[2].items():
                        xml = re.sub(ur'<{0}>(.*)</{0}>'.format(attr_name),
                                     u'<{0}>{1}</{0}>'.format(attr_name, '<![CDATA[{0}]]>'.format(attr_value)), xml)
                    # remove non-settable fields
                    xml = re.sub(r'<id_default_image(.+)</id_default_image>', '', xml)
                    xml = re.sub(r'<position_in_category(.+)</position_in_category>', '', xml)
                    xml = re.sub(r'<manufacturer_name(.+)</manufacturer_name>', '', xml)
                    xml = re.sub(r'<associations>(.+)</associations>(?s)', '', xml)
                    # replace price with base_price
                    base_price = re.findall(ur'<base_price>(.*)</base_price>', xml)[0]
                    xml = re.sub(ur'(?<=<price>)(.*)(?=</price>)', base_price, xml)
                    # replace quantity. it's not writable anymore
                    xml = re.sub(r'<quantity(.*)</quantity>', '', xml)

                    req = urllib2.Request(str("http://%s/api/%s" % (domain, resource)),
                                          headers={'Content-Type': 'application/x-www-form-urlencoded',
                                                   'Authorization': authheader})
                    req.get_method = lambda: 'PUT'
                    urllib2.urlopen(req, data=xml.encode('utf-8'))
                    total_price += 1
                except urllib2.HTTPError as e:
                    err_msg = e.fp.read()
                    total_results['errors'].append({'message': str(e), 'details': err_msg,
                                                    'product': id,
                                                    'combination': int(id_attribute)})
                except HTTPException as e:
                    total_results['errors'].append({'message': str(e), 'details': e.message,
                                                    'product': id,
                                                    'combination': int(id_attribute)})
            # END PRICE ---------------------------------

            # Quantity is not present for main product with combinations
            if 'quantity' in row[2]:
                # find right stock id
                stocks = get_xml_data("http://%s/api/%s?filter[id_product]=[%s]&filter[id_product_attribute]=[%s]"
                                      % (domain, 'stock_availables', id, id_attribute), headers)
                stock_id = stocks.findall('.//stock_available')
                if stock_id:
                    stock_id = stock_id[0].attrib['id']
                    req = urllib2.Request("http://%s/api/%s/%s" % (domain, 'stock_availables', stock_id),
                                          headers={'Content-Type': 'text/xml',
                                                   'Authorization': authheader})
                    xml = urllib2.urlopen(req).read()
                    xml = clean_chunked_data(xml)
                    xml = xml.decode('utf-8')
                    for attr_name, attr_value in row[2].items():
                        xml = re.sub(r'<{0}>(.*)</{0}>'.format(attr_name),
                                     '<{0}>{1}</{0}>'.format(attr_name, attr_value), xml)

                    # TODO: write test for it, otherwise prestashop returns error
                    if id_attribute == '0':
                        xml = xml.replace('<id_product_attribute></id_product_attribute>',
                                          '<id_product_attribute>0</id_product_attribute>')

                    # TODO: write test for depends on stock
                    if '<depends_on_stock><![CDATA[1]]></depends_on_stock>' in xml:
                        depends_on_stock = True
                        continue

                    try:
                        req = urllib2.Request(str("http://%s/api/%s/%s" % (domain, 'stock_availables', stock_id)),
                                              headers={'Content-Type': 'application/x-www-form-urlencoded',
                                                       'Authorization': authheader})
                        req.get_method = lambda: 'PUT'
                        urllib2.urlopen(req, data=xml.encode('utf-8'))
                        total_count += 1
                    except urllib2.HTTPError as e:
                        err_msg = e.fp.read()
                        total_results['errors'].append({'message': str(e), 'details': err_msg,
                                                        'product': id, 'combination': int(id_attribute)})
                    except HTTPException as e:
                        total_results['errors'].append({'message': str(e), 'details': e.message,
                                                        'product': id, 'combination': int(id_attribute)})
                else:
                    # stock not available, report it
                    total_results['errors'].append({'message': _('No stock available'), 'details': _('No stock available'),
                                                    'product': id, 'combination': int(id_attribute)})
        if depends_on_stock:
            total_results['result'] = '15_depends_on_stock'
        if total_count or total_price:
            total_results['result'] = 'update_ok'
        else:
            total_results['result'] = '14_update_permission'
        total_results['count'] = total_count
        return total_results

    def add_product_data(self, data_list, images):
        """
        :param data_list: list of product data in the following form:
        [{'ean13':EAN13, 'price':PRICE, 'categories':[MAIN_CATEGORY, OTHER,...],
          'langs': ['id':LANG_ID, 'name':PRODUCT_NAME, 'link_rewrite': link_rewrite]},...]
        see how these fields are generated in AddProductsShopForm.clean() method.
        :param images: list of images for every product
        :return: update_ok string if everything is fine, error string that matches
                 HTML ID in template otherwise
        """

        # Check default lang, add link rewrite if it is different
        default_lang = self.default_lang
        for prod in data_list:
            langs = set([lang['id'] for lang in prod['langs']])
            if default_lang not in langs:
                new_value = prod['langs'][0].copy()
                new_value['id'] = default_lang
                prod['langs'].append(new_value)

        domain = self.shop.domain
        headers = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Authorization': self.shop.authheader}

        context = {'prestashop_url': domain, 'products': data_list,
                   'date_add': datetime.now()}

        products_xml = render_to_string('xml_templates/add_products15.xml', context).encode('utf-8')

        try:
            result = get_xml_data("http://%s/api/products" % domain,
                                  headers, urllib.urlencode({'xml': products_xml}))
            # Extract product ids
            product_ids = [e.text for e in result.findall('.//product/id')]

            # TODO: Prestashop 1.5 does not allow to set quantities simalteniously,
            # set them separately
            quantities = [x['quantity'] for x in data_list]
            update_data_list = [(p_id, '0', {'quantity': str(q)}) for p_id, q in zip(product_ids, quantities)]
            self.update_presta_data(update_data_list)
            # IMAGES ADD CODE
            self.add_images.delay(self, product_ids, images)

        except urllib2.HTTPError, e:
            result = e.fp.read()
            send_email.delay('mail/error', {'domain': domain, 'message': str(result),
                                            'data_list': str(data_list),
                                            'full_data': ''}, "Add product client Error")
            return '14_update_permission_or_csv'
        return "14_create_products"
