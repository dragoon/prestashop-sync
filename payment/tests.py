from datetime import date, timedelta

from django.conf.urls import patterns, url
from django.http import Http404, HttpResponse
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.views.generic import View

from payment.views import PaymentSuccess


class TestPaymentResponse(View):
    """Imitates PAYPAL response, used in tests"""
    def get(self, request, *args, **kwargs):
        tx_id = self.request.GET['tx']
        if tx_id == '1234':
            return HttpResponse('SUCCESS\n'
                                'mc_gross=5.00\n'
                                'payment_status=Pending')
        raise Http404

    @staticmethod
    def paypal_post(tx_id):
        from django.test import Client
        c = Client()
        response = c.get(reverse('paypal_test') + '?tx={}'.format(tx_id))
        return response.content.split()

# replace function
PaymentSuccess.paypal_post = staticmethod(TestPaymentResponse.paypal_post)

from presta.urls import urlpatterns

urlpatterns += patterns('',
    url(r'^payment/test_paypal/$', TestPaymentResponse.as_view(), name='paypal_test'),
)


class PaymentTest(TestCase):
    """Test basic payment functionality"""
    fixtures = ('payment_test_data',)

    def test_incorrect_transaction(self):
        self.assertTrue(self.client.login(username='test@gmail.com', password='a'))
        response = self.client.get(reverse('payment_success') + '?tx=XXXX')
        self.assertTemplateUsed(response, template_name='payment/failure.txt')

    def test_custom_amount(self):
        self.assertTrue(self.client.login(username='test@gmail.com', password='a'))
        self.client.get(reverse('payment_success') + '?tx=1234')

        # Check plan expiry updated
        from users.models import Profile
        user = Profile.objects.get(email='test@gmail.com')
        self.assertEquals(date.today() + timedelta(days=10), user.plan_expiry)
