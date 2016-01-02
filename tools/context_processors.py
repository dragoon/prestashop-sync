# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import ugettext_lazy as _

def langs(request):
    """
    A context processor that returns a list of available languages and sets active language
    """
    cur_lang = get_language()
    return {
        'langs': [{'lang': lang, 'title': _(title)} for lang, title in settings.LANGUAGES],
        'current_lang': cur_lang
    }

def manual_url(request):
    """
    Get correct manual url for the LANGUAGE in request
    """
    cur_lang = get_language()
    cur_lang = cur_lang.split('-')[0]
    # TODO: this is quite dirty as it does not involve usage of reverse
    return {'manual_url': '/manual_%s' % cur_lang}

