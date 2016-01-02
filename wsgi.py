import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ['CELERY_LOADER'] = 'django'
path = os.path.dirname(__file__)
if path not in sys.path:
    sys.path.insert(0, path)
    sys.path.insert(0, os.path.join(path, 'external'))

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
