from django.conf import settings
from django.conf.urls import *

from django.views.generic.base import TemplateView

urlpatterns = patterns('tools.views',
    url(r'^send_error$', 'send_error', name='send_error'),
    url(r'^change_lang/(?P<lang>\w{2})$', 'change_lang', name='change_lang'),
    #url(r'^create_superuser$', 'create_superuser', name='create_superuser'),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        url(r'^404$', TemplateView.as_view(template_name='404.html')),
        url(r'^500$', TemplateView.as_view(template_name='500.html')),
    )
