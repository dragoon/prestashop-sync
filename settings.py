import os.path

DEBUG = True
TEMPLATE_DEBUG = DEBUG
LOGGING_LOG_SQL = DEBUG

INTERNAL_IPS = ('127.0.0.1',)

PS_VERSION = '3.5 update 15'

SITE_ID = 1

ADMINS = (
)
ADMIN_MAILS = [email for name, email in ADMINS]

MANAGERS = ADMINS

#-------- I18N settings ---------------------
USE_I18N = True
LANGUAGE_CODE = 'en'

ugettext = lambda s: s

LANGUAGES = (
    ('en', ugettext('English')),
    ('ru', ugettext('Russian')),
)
#---------------- APPs ----------------

TIME_ZONE = 'Europe/Moscow'
SECRET_KEY = ''

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.markup',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sites',
    'django.contrib.syndication',
    'django.contrib.messages',
    'south',
    'djcelery',
    'kombu.transport.django',
    'presta',
    'payment',
    'users',
    'tools',
    'external.articles',
    'compressor',
    'django_coverage',
    'paypal.standard.ipn',
    #'django_memcached',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.AuthenticationMiddleware',
)

ROOT_URLCONF = 'urls'

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.request',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.contrib.messages.context_processors.messages',
    'presta.context_processors.show_help',
    'presta.context_processors.csv_files',
    'tools.context_processors.langs',
    'tools.context_processors.manual_url',
    'payment.context_processors.paypal',
    'external.articles.context_processors.article_count',
)

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))

TEMPLATE_DIRS = (os.path.join(PROJECT_DIR, 'templates'),)
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    #     'django.template.loaders.eggs.Loader',
)
LOCALE_PATHS = (
    os.path.join(PROJECT_DIR, 'locale'),
)

AUTHENTICATION_BACKENDS = (
    'users.auth_backends.EmailModelBackend',
    'users.auth_backends.LoginzaModelBackend',
    'users.auth_backends.EmailPasswordBackend'
)

LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/login'

#-------------TESTING--------------
TEST_RUNNER = 'tools.test_runner.MyTestSuiteRunner'
COVERAGE_REPORT_HTML_OUTPUT_DIR = 'coverage'
COVERAGE_MODULE_EXCLUDES = ('djcelery', 'djkombu', 'settings$', 'urls$',
                            'locale$', '__init__', 'django', 'migrations')
COVERAGE_REPORT_THEME = 'rcov'
#------------------------------------

#--------- ARTICLES APP ------------
DISQUS_FORUM_SHORTNAME = 'prestasync'
#-----------------------------------

import djcelery
djcelery.setup_loader()

PAGINATION = 50

#----------------Demo shop setting-----------------------
DEMO_SHOP = {'domain':'www.presta-test.com', 'sync_type': 'EAN13', 'key':'5SIWF2EECP25TZLELM30RGUT8FBBHRD8'}
DEMO_SHOP_FULL = dict(DEMO_SHOP.items() +
                      dict(title='Presta-Test', version='1.4', status='green',
                           location='http://www.presta-test.com/update.csv').items())

#--------------- LOGGING --------------------------------------
# Requires django 1.3
LOGGING = {
    'version': 1,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
            }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

DJANGO_MEMCACHED_REQUIRE_STAFF = True
PAYPAL_RECEIVER_EMAIL = "EMPTY"

from site_settings import *
