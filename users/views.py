# -*- coding: utf-8 -*-
from django.contrib.auth import login as auth_login, authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.utils import simplejson
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, FormView
from django.views.generic.simple import direct_to_template
from django.utils.translation import ugettext as _
from presta.utils.shop_utils import transfer_objects
from presta.views import prepopulate

from users.loginza_api import get_auth_info, parse_result
from users.forms import RegisterForm, RequestEmailForm, UserLoginForm, DeleteUserForm
from users.models import Profile
from users.utils import generate_activation_key
from tools.utils import send_email


class RegisterAjax(TemplateView):
    template_name = "users/register_ajax.html"

    def get_context_data(self, plan, **kwargs):
        """Return correct initial plan depending on the user's choice"""
        # convert plan to int to properly render custom select
        plan = int(plan)
        context = super(RegisterAjax, self).get_context_data(**kwargs)
        context['register_form'] = RegisterForm(initial={'plan': plan})
        return context


@never_cache
def login(request, template="users/login.html"):
    """Displays the login form and handles the login action."""

    if request.method == "POST":
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()

            return HttpResponse(simplejson.dumps({'response': '/', 'result': 'success'}))
        else:
            response = {}
            for k,v in form.errors.items():
                response[k] = v
            return HttpResponse(simplejson.dumps({'response': response, 'result': 'error'}))

    login_form = UserLoginForm(request)
    register_form = RegisterForm
    request.session.set_test_cookie()

    return direct_to_template(request, template,
                              extra_context={'login_form': login_form,
                                             'register_form':register_form})


@csrf_exempt
def loginza_login(request):
    if request.method=='POST':
        token=request.POST.get('token')
        if token:
            result = simplejson.loads(get_auth_info(token))
            # Check if there is an error - like token was used previously
            if result.has_key('error_message'):
                # TODO: redirect to page with error message and ask for relogin
                send_email.delay('mail/error', {'message': str(result)}, "Loginza Error")
                raise Http404
            uid, provider, defaults = parse_result(result)
            if not (defaults['email'] or Profile.objects.filter(uid=uid, provider=provider).exists()):
                form = RequestEmailForm(request=request)
                request.session['token'] = result
                return direct_to_template(request, "users/request_email.html", extra_context={'form': form })
            user = register_loginza_user(uid, provider, defaults, request)
            return HttpResponseRedirect(user.get_register_redirect())
    raise Http404


@prepopulate(RequestEmailForm, "users/request_email.html")
def add_email(request, form):
    result = request.session.get('token')
    if result:
        uid, provider, defaults = parse_result(result)
        defaults['email'] = form.cleaned_data['email']

        if Profile.objects.filter(email=defaults['email']).exists():
            return HttpResponse(simplejson.dumps({'response':
                            {'email':_('User with this email already exists')}, 'result': 'error'}))

        del request.session['token']
        user = register_loginza_user(uid, provider, defaults, request)
        return HttpResponse(simplejson.dumps({'response': user.get_register_redirect(), 'result': 'success'}))
    raise Http404


def register_loginza_user(uid, provider, defaults, request):
    """
    Register user in the system from Loginza OpenID
    :rtype: Profile
    """
    # Check if user already exists but uses different OpenID
    if 'email' in defaults:
        try:
            user = Profile.objects.get(email=defaults['email'])
        except Profile.DoesNotExist:
            pass
        else:
            user = authenticate(email=user.email)
            auth_login(request, user)
            return user

    user, created = Profile.objects.get_or_create(uid=uid, provider=provider,
                                                  is_active=True, defaults=defaults)
    if created:
        user.set_unusable_password()
        user.save()
        transfer_objects(request.user, user)
    user = authenticate(uid=uid, provider=provider)
    if user.is_active:
        auth_login(request, user)
    return user

@require_POST
def register(request):
    form = RegisterForm(request.POST)
    if form.is_valid():
        user = form.save(commit=False)

        # Generate activation key for user account
        activation_key = generate_activation_key(user.email)
        user.activation_key = activation_key
        user.is_active = False
        user.save()

        send_email.delay('mail/confirmation', {'link': activation_key},
                   u'\u2713 ' + _("Welcome to Prestashop-Sync Service"), [user.email])
        return HttpResponse(simplejson.dumps({'response': _("Email with a confirmation link has been sent"),
                                       'result': 'success'}))
    else:
        response = {}
        for k in form.errors:
            response[k] = form.errors[k][0]
        return HttpResponse(simplejson.dumps({'response': response, 'result': 'error'}))


class DeleteUserView(FormView):
    form_class = DeleteUserForm

    def form_valid(self, form):
        """delete and redirect to main page"""
        self.request.user.delete()
        return HttpResponseRedirect(reverse('main'))


def confirm(request, activation_key):
    if not request.user.is_guest():
        return HttpResponseRedirect('/')
    user = get_object_or_404(Profile, activation_key=activation_key)

    # Activate then login user
    if not user.is_active:
        user.is_active = True
        user.save()
        transfer_objects(request.user, user)
        user = authenticate(email=user.email)
        auth_login(request, user)

    return HttpResponseRedirect(user.get_register_redirect())
