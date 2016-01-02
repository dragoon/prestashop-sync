from django import http
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils import simplejson
from django.views.decorators.csrf import requires_csrf_token
from django.views.generic.simple import redirect_to
from django.template import Context, loader
from django.utils.translation import ugettext as _
from django.utils.translation import activate

from presta.views import prepopulate
from tools.forms import ContactForm
from tools.utils import send_email


def create_superuser(request):
    username = request.GET.get('username', 'admin')
    email = request.GET.get('email', 'admin@prestashop-sync.com')
    password = request.GET.get('password', 'bugoga')
    User.objects.create_superuser(username, email, password)
    return HttpResponse("ok")


def send_error(request):
    if request.method == 'POST':
        send_email.delay('mail/js_error', request.POST, "JavaScript Error")
    return HttpResponse("ok")


def change_lang(request, lang):
    request.session['django_language'] = lang
    activate(lang)
    next_url = request.GET.get('next', '/')
    # properly change lang for manual pages
    if next_url.endswith('ru/') and lang == 'en':
        next_url = next_url.replace('ru/', 'en/')
    else:
        next_url = next_url.replace('en/', 'ru/')
    return redirect_to(request, next_url)


@prepopulate(ContactForm, 'contacts.html')
def contact(request, form):
    form.notify()
    result = {'result': 'success', 'response': _('We have received your message. Thank you!')}
    return HttpResponse(simplejson.dumps(result))


@requires_csrf_token
def server_error(request, template_name='500.html'):
    """
    500 error handler.

    Templates: `500.html`
    Context:
        STATIC_URL
            Path of static static (e.g. "static.example.org")
    """
    t = loader.get_template(template_name)  # You need to create a 500.html template.
    return http.HttpResponseServerError(t.render(Context({
        'STATIC_URL': settings.STATIC_URL, 'request': request
    })))
