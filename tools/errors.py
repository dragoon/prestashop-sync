import hashlib

from django.core.cache import cache
from django.utils.translation import ugettext as _

from tools.context_processors import manual_url


class PrestaError(Exception):
    KEY = "key"
    DOMAIN = "domain"
    API_PHP_INSTALL = _('Please install api.php file')
    REGEN_HTACCESS = _('Please regenerate .htaccess file')
    NO_PRODUCTS = _('No products found')
    NOT_REACHABLE = _('URL is not reachable')
    NOT_ACTIVATED = _('Please activate web-service')
    PROD_OPTIONS_VALUES = _('Enable product_option_values checkbox')
    PROD_COMBINATIONS = _('Enable combinations checkbox')

    @staticmethod
    def get_error(key, value, api):
        """Set cache key to customize error message if we get the same more than once"""
        #TODO: may be put this into session, but need to think about cleaning them
        user_id = api.shop.user.user_id
        cache_key = hashlib.sha256(key+"|"+value+"|"+str(user_id)).hexdigest()
        if cache.get(cache_key):
            value = _(value)+ ', <a target="_blank" href="%s#%s">%s<a/>' %\
                              (manual_url(None)['manual_url'], api.__version__,_('instructions'))
        else:
            cache.set(cache_key, value, 300)
            value = _(value)
        return {key: value}

    @classmethod
    def rewrite_disabled(cls, error_dict):
        if error_dict.has_key(cls.DOMAIN) and \
           error_dict[cls.DOMAIN].startswith(_(cls.API_PHP_INSTALL)):
            return True
        return False

