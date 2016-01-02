from django.conf import settings

if settings.DEBUG:
    PAYPAL_URL='https://www.sandbox.paypal.com/cgi-bin/webscr'
    PAYPAL_TOKEN=''
    PAYPAL_BUTTON_ID=''
else:
    PAYPAL_URL='https://www.paypal.com/cgi-bin/webscr'
    PAYPAL_TOKEN=''
    PAYPAL_BUTTON_ID=''



