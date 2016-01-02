import httplib
import re

_re_url_remove = re.compile(r"[^a-zA-Z0-9\-:.,'()]+")

def get_auth_info(token):
    conn = httplib.HTTPConnection("loginza.ru")
    conn.request("POST", "/api/authinfo?token=%s" % token)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return data

def parse_result(data_dict):
    """
    :type data_dict: dict
    :return: uid, provider, other attributes
    """
    result_dict = {}
    name_dict = data_dict.get('name') or {}
    first_name = name_dict.get('first_name')
    last_name = name_dict.get('last_name')
    full_name = name_dict.get('full_name')

    names = [first_name, last_name]
    if full_name:
        for i, name in enumerate(full_name.split(' ', 1)):
            names[i] = names[i] or name
    result_dict['first_name'], result_dict['last_name'] = names
    result_dict['gender'] = data_dict.get('gender')
    # DOB will be always null for now
    result_dict['dob'] = None
    result_dict['email'] = data_dict.get('email')

    uid = data_dict.get('uid') or data_dict.get('identity')
    return uid, data_dict['provider'], result_dict
