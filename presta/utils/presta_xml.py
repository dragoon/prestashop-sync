import urllib2

from lxml import etree
from lxml.etree import XMLSyntaxError


def clean_chunked_data(html_data):
    # A set of checks for chunked encoding
    xml_start = html_data.find('<?xml')
    if xml_start!=-1:
        html_data = html_data[xml_start:]
    xml_end = html_data.rfind('</prestashop>')
    if xml_end!=-1 and xml_end != len(html_data) - 14:
        html_data = html_data[:xml_end + 13]

    # replace weird characters here, like ^C (\x03)
    html_data = html_data.replace('\x03', '')
    return html_data


def get_xml_data(req_string, headers, data=None):
    req = urllib2.Request(req_string, headers=headers)
    html_data = _get_html_data(req, data)
    # Clean chunked data
    html_data = clean_chunked_data(html_data)
    #log_user_action(req.get_host() ,'chunked data', html_data, {})

    try:
        data = etree.fromstring(html_data)
    except XMLSyntaxError:
        # lxml cannot handle encoding declarations :(
        data = etree.HTML(html_data, etree.HTMLParser())
        # data is None when it was not XML, like 404 page without 404 code
        if data is not None:
            data = data.getroottree()
        else:
            raise urllib2.HTTPError(req_string, 404, "Not an XML", None, None)
        # TODO: check valid
        #if not data.find('.//prestashop'):
        #    raise urllib2.HTTPError(req_string, 404, "Not an XML", None, None)
    return data


def _get_html_data(req, data, attempts=2):
    #TODO: may be add requests library here
    html_data = None
    for i in range(attempts):
        try:
            html_data = urllib2.urlopen(req, data=data, timeout=60).read()
            break
        except urllib2.URLError:
            pass
    # Try last time with exception raising
    if not html_data:
        html_data = urllib2.urlopen(req, data=data, timeout=60).read()
    return html_data
