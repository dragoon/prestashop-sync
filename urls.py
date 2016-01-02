from django.conf.urls import *
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import logout
from django.contrib import admin
from django.views.generic import TemplateView
from payment.views import PaymentSuccess, PaymentPage
from presta.forms import DivErrorList
from presta.views import MainView
from users.utils import not_guest_required
from users.views import RegisterAjax, DeleteUserView
from users.forms import SetPasswordForm


def password_reset_form(*args, **kwargs):
    """Custom error form"""
    return PasswordResetForm(*args, error_class=DivErrorList, **kwargs)


admin.autodiscover()

urlpatterns = patterns('',
    (r'^master/', include(admin.site.urls)),
)

urlpatterns += patterns('users.views',
    url(r'^register/$', 'register', name='register'),
    url(r'^confirm/(\w{40})/$', 'confirm', name='confirm'),
    url(r'^login_ajax/$', 'login', {'template': 'users/login_ajax.html'}, name='login_ajax'),
    url(r'^register_ajax/(?P<plan>\d+)$', RegisterAjax.as_view(), name='register_ajax'),
    url(r'^login/$', 'login', {'template': 'users/login.html'}, name='login'),
    url(r'^loginza_login/$', 'loginza_login', name='loginza_login'),
    url(r'^loginza_XXX.html$',
        TemplateView.as_view(template_name="loginza_verify.html"), name='loginza_verify'),
    url(r'^logout/$', logout, {'next_page': '/'}, name='logout'),
    url(r'^add_email/$', 'add_email', name='add_email'),

    url(r'^battery_ajax/$', TemplateView.as_view(template_name="partial/headers/battery_left.html"),
        name='battery'),
)

urlpatterns += patterns('django.contrib.auth.views',
    url(r'^password/reset/$', 'password_reset',
        {'template_name': 'users/reset/password_reset.html',
         'email_template_name': 'users/reset/password_reset_email.html',
         'password_reset_form': password_reset_form}, name='password_reset'),
    url(r'^password/reset/done/$', 'password_reset_done',
        {'template_name': 'users/reset/password_reset_done.html'},
        name='password_reset_done'),
    url(r'^password/reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$',
        'password_reset_confirm',
        {'template_name': 'users/reset/password_reset_confirm.html',
         'set_password_form': SetPasswordForm},
        name='password_reset_confirm'),
    url(r'^password/reset/complete/$', 'password_reset_complete',
        {'template_name': 'users/reset/password_reset_complete.html'},
        name='password_reset_complete'),
)

urlpatterns += patterns('',
    (r'^articles/', include('external.articles.urls')),
)

urlpatterns += patterns('',
    (r'^tools/', include('tools.urls')),
)

urlpatterns += patterns('',
    (r'^', include('presta.urls')),
)

urlpatterns += patterns('',
    url(r'^$', MainView.as_view(), name='main'),
    url(r'^about/$', TemplateView.as_view(template_name="about.html"), name='about'),
    url(r'^manual_ru/$', TemplateView.as_view(template_name="manual_ru.html"), name='manual_ru'),
    url(r'^manual_en/$', TemplateView.as_view(template_name="manual_en.html"), name='manual_en'),
    url(r'^en/terms/$', TemplateView.as_view(template_name="terms.html"), name='terms'),
    url(r'^en/policy/$', TemplateView.as_view(template_name="policy.html"), name='policy'),
    url(r'^ru/terms/$', TemplateView.as_view(template_name="terms.html"), name='terms_ru'),
    url(r'^ru/policy/$', TemplateView.as_view(template_name="policy.html"), name='policy_ru'),
    url(r'^options/$', TemplateView.as_view(template_name="payment/options.html"),
        name='pay_options'),
    url(r'^payment/$', not_guest_required(PaymentPage.as_view()), name='payment'),
    url(r'^payment_small_business/$', not_guest_required(PaymentPage.as_view(small_business=True)),
        name='payment_small_business'),
    url(r'^account/$', not_guest_required(TemplateView.as_view(template_name="users/account.html")),
        name='account'),
    url(r'^account/delete/$', not_guest_required(DeleteUserView.as_view()), name='account_delete'),
    url(r'^payment/success/$', PaymentSuccess.as_view(), name='payment_success'),
    url(r'^payment/cancel/$', TemplateView.as_view(template_name="payment/cancel.html"),
        name='payment_cancel'),
    (r'^payment/IPN/trytoguessit/', include('paypal.standard.ipn.urls')),
)

urlpatterns += patterns('tools.views',
    url('^contacts/$', 'contact', name='contacts'),
)

urlpatterns += patterns('',
    (r'^cache/', include('django_memcached.urls')),
)
handler500 = 'tools.views.server_error'
