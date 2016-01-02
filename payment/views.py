from django.contrib import messages
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import SimpleTemplateResponse
from django.views.generic import TemplateView
import requests

from payment import settings
from users.models import Profile
from tools.utils import send_email


class PaymentPage(TemplateView):
    """
    View to not show the current plan on the payment page,
    we don't want to confuse with seeing "free plan".
    """
    template_name = "payment/payment.html"
    small_business = False

    def get_context_data(self, **kwargs):
        context = super(PaymentPage, self).get_context_data(**kwargs)
        context['show_upgrage'] = True
        context['small_business'] = self.small_business
        return context


class PaymentSuccess(TemplateView):
    """
    For displaying payment success information
    Subscription dict: ['SUCCESS', 'transaction_subject=Prestashop+Sync+business',
                'txn_type=subscr_payment', 'payment_date=13%3A00%3A40+Jan+31%2C+2013+PST',
                'subscr_id=XXX', 'last_name=XXX', 'residence_country=US',
                'pending_reason=multi_currency', 'item_name=Prestashop+Sync+business',
                'payment_gross=', 'mc_currency=EUR', 'business=EMAIL',
                'payment_type=instant', 'protection_eligibility=Ineligible', 'payer_status=verified',
                'payer_email=EMAIL', 'txn_id=XXX',
                'receiver_email=EMAIL', 'first_name=Roman',
                'payer_id=XXX', 'receiver_id=XXX', 'item_number=PSBIZ',
                'payment_status=Pending', 'btn_id=XXX', 'mc_gross=15.00', 'charset=windows-1252']
    """
    template_name = "payment/payment.html"

    @staticmethod
    def paypal_post(tx_id):
        """
        Make a request to paypal.
        It's a separate function to be replaced in testing
        """
        r = requests.get(settings.PAYPAL_URL, verify=False,
                          params={'cmd': '_notify-synch', 'tx': tx_id, 'at': settings.PAYPAL_TOKEN})
        return r.content.split()

    def get_context_data(self, *args, **kwargs):
        context = super(PaymentSuccess, self).get_context_data(**kwargs)
        tx = self.request.GET.get('tx')
        if not tx:
            return context

        results = PaymentSuccess.paypal_post(tx)
        send_email.delay('mail/feedback', {'message': str(results), 'email': self.request.user.email},
                         'User payment validation')
        context['result'] = (results[0] == 'SUCCESS')
        if context['result']:
            result_dict = dict(res.split('=') for res in results[1:])
            amount_paid = result_dict.get('mc_gross')
            if not amount_paid or int(float(amount_paid)) < 3:
                context['result'] = False
            elif result_dict.get('payment_status') in ('Pending', 'Completed', 'Created', 'Processed'):
                amount_paid = int(float(amount_paid))
                user = self.request.user
                """:type: Profile"""
                item_name = result_dict.get('item_name')
                if 'small' not in item_name:
                    user.plan = Profile.PLAN_BUSINESS
                else:
                    user.plan = Profile.PLAN_SMALL_BUSINESS
                user.plan_expiry = user.new_plan_expiry(amount_paid)
                # https://cms.paypal.com/uk/cgi-bin/?cmd=_render-content&content_ID=developer/e_howto_html_IPNandPDTVariables
                if result_dict.get('txn_type') == 'subscr_payment':
                    user.subscription = True
                user.save()
        return context

    def get(self, request, *args, **kwargs):
        """Add message and perform redirect to get rid of paypal GET parameters"""

        context = self.get_context_data(**kwargs)
        if 'result' not in context:
            raise PermissionDenied

        if context['result']:
            template = 'payment/success.txt'
        else:
            template = 'payment/failure.txt'
        message = SimpleTemplateResponse(template, context).rendered_content
        messages.info(request, message)
        return HttpResponseRedirect(reverse('account'))
