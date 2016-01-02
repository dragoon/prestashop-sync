import csv
from functools import wraps
from django.forms.formsets import formset_factory

from django.forms.models import modelformset_factory

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.functional import curry
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import ListView

#from django.contrib import messages
from django.views.generic.simple import direct_to_template
from django.http import HttpResponse, Http404, HttpResponseNotFound
from django.utils import simplejson
from django.utils.translation import ugettext as _

from presta.forms import LoadDataForm, DivErrorList, LoadDataSingleForm, LoadDataBaseForm,\
    AddShopForm, EditShopForm, AddProductsShopForm, AddProductsShopBaseFormSet, ActivationForm,\
    UpdateProductValidator
from presta.models import Shop, UpdateStatus
from presta.tasks import checked_update_presta_data_task
from presta.utils.shop_utils import update_shop_status, wait_for_shop_status
from tools.errors import PrestaError


def prepopulate(form_class, template=None):
    def inner(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method == 'POST':
                form = form_class(request.POST, request.FILES, request=request)
                if form.is_valid():
                    return view(request, form, *args, **kwargs)
                else:
                    response = {}
                    for k, v in form.errors.items():
                        response[k] = v
                    return HttpResponse(simplejson.dumps({'response': response, 'result': 'error'}))
            if template:
                return direct_to_template(request, template,
                                          extra_context={'form': form_class(request=request)})
            raise Http404
        return wrapper
    return inner


@prepopulate(LoadDataForm)
def update_data(request, form):
    if not request.user.is_update_allowed():
        raise Http404
    request.session['shop'] = shop = form.get_shop(True)
    csv_file = form.cleaned_data['csv_file']

    # Get presta data
    try:
        result = shop.prepare_data_for_update(csv_file)
    except ValueError:
        # TODO: write test for it
        result = {'result': 'error', 'response': {'csv_file': _('File is not valid')}}
    if result['result'] == 'success':
        # Remove CSV file from session if exists
        if request.session.get(LoadDataForm.CSV_FILE_NAME):
            del request.session[LoadDataForm.CSV_FILE_NAME]

        language = request.session.get('django_language', 'en')
        checked_update_presta_data_task(shop, result['response'], language)
        result['response'] = 'ok'
        shop.send_data_update_signal()
    return HttpResponse(simplejson.dumps(result))


def add_data(request, pk):
    shop = get_object_or_404(Shop, pk=pk, user=request.user)

    # Hack to supply additional argument to the AddProdutsShopForm
    AddProductsShopFormSet = formset_factory(AddProductsShopForm,
                                             formset=AddProductsShopBaseFormSet)
    AddProductsShopFormSet.form = staticmethod(curry(AddProductsShopForm, shop=shop))

    formset = AddProductsShopFormSet(request.POST or None)
    if request.method == 'POST':
        # Set csv file, we later access it in clean method
        try:
            formset.csv_file = request.session.pop(AddProductsShopForm.CSV_FILE_NAME)
            formset.csv_file.shop = shop
        except KeyError:
            pass
        if formset.is_valid():
            images = []
            data_list = []
            for form in formset:
                data_list.append(form.cleaned_data)
                try:
                    images.append(request.session.pop('product_%d' % form.cleaned_data['order']))
                except KeyError:
                    pass
            response = shop.api.add_product_data(data_list, images)
            return HttpResponse(simplejson.dumps({'response': response, 'result': 'success'}))
        else:
            response = {}
            for form in formset:
                order = form.data[form.prefix + '-order'][0]
                for k, v in form.errors.items():
                    response['form-%s-%s' % (order, k)] = v
            return HttpResponse(simplejson.dumps({'response': response, 'result': 'error'}))
    return direct_to_template(request, template="partial/shop_add_products.html",
                              extra_context={'formset': formset, 'shop': shop})


def add_images(request, product_id):
    from StringIO import StringIO
    products = request.session.get('product_' + product_id, [])
    for image in request.FILES.values():
        img_file = StringIO(image.read())
        img_file.name = image._name
        products.append(img_file)
    request.session['product_' + product_id] = products
    return HttpResponse(simplejson.dumps({'response': _("Drag images here.")}))


def remove_images(request, product_id):
    try:
        i = int(request.POST.get('i'))
        del request.session['product_' + product_id][i]
    except (IndexError, KeyError):
        pass
    request.session.modified = True
    return HttpResponse("ok")


def upload_csv(request, form_class):
    """
    Upload csv file to server and validate it.
    :param form_class: - form class to instantiate (taken from urls.py)
    :rtype: HttpResponse
    """
    csv_file = request.FILES.get('0')
    if csv_file:
        # Apply custom validation
        new_csv_file = None
        try:
            new_csv_file = form_class.validate_csv_file(csv_file)
        except Exception:
            pass
        if not new_csv_file:
            return HttpResponseNotFound(simplejson.dumps({'response': _('File is not valid')}))
        else:
            response = {'response': _('File is valid'), 'lines': new_csv_file.line_count,
                        'names': new_csv_file.names}
            if new_csv_file.warning:
                # add warning
                response['warning'] = new_csv_file.warning
                response['response'] = _('File is partially valid')
            request.session[form_class.CSV_FILE_NAME] = new_csv_file
        return HttpResponse(simplejson.dumps(response))
    raise Http404


@require_POST
def clear_csv(request, form_class):
    """
    :param request: HttpRequest
    :param form_class: form class to instantiate (taken from urls.py)
    :return: HttpResponse
    """
    if request.session.get(form_class.CSV_FILE_NAME):
        del request.session[form_class.CSV_FILE_NAME]
    return HttpResponse()


@prepopulate(LoadDataBaseForm)
def check_update(request, form):
    """
    :type form: LoadDataBaseForm
    """
    domain = form.cleaned_data['domain']
    try:
        status = UpdateStatus.objects.get(domain=domain)
        return HttpResponse(simplejson.dumps({'result': status.update_status}))
    except UpdateStatus.DoesNotExist:
        return HttpResponse(simplejson.dumps({'result': 'wait'}))


@prepopulate(LoadDataSingleForm)
def update_data_single(request, form):
    """
    :type form: LoadDataSingleForm
    """
    if not request.user.is_update_allowed():
        raise Http404
    shop = form.get_shop()
    data_list = form.get_data(request)
    result = shop.api.update_presta_data(data_list)['result']
    shop.send_data_update_signal()
    return HttpResponse(simplejson.dumps({'response': result, 'result': 'success'}))


@prepopulate(LoadDataBaseForm)
def get_data(request, form):
    """
    :type form: LoadDataBaseForm
    """
    # TODO: test get_data when there are < 50 products, but > 50 combinations
    request.session['shop'] = shop = form.get_shop(True)
    data, error_dict = shop.get_data()
    if error_dict:
        return HttpResponse(simplejson.dumps({'response': error_dict, 'result': 'error'}))

    next = shop.is_data_finished(len(data), 1)
    # put (data, real page number, start page index)
    request.session['data'] = (data, 0, 0)
    if len(data) > settings.PAGINATION:
        data = data[:settings.PAGINATION]
    request.session['sync_type'] = shop.sync_type

    from tools.utils import send_email
    send_email.delay('mail/error', {'domain': shop.domain}, "Successful GetData")

    response = render_to_string('partial/products_table.html', {'data': data,
                                                                'sync_type': shop.sync_type,
                                                                'next': next,
                                                                'previous': 0,
                                                                'start_index': 0})
    return HttpResponse(simplejson.dumps({'response': unicode(response),
                                          'result': 'success', 'temp': shop.temp}))


@prepopulate(LoadDataBaseForm)
def get_data_paginated(request, form, page):
    """
    :type form: LoadDataBaseForm
    """
    request.session['shop'] = shop = form.get_shop()

    data, real_page, total_count = request.session['data']
    page = int(page)
    if page < total_count:
        # Going previous
        real_page -= 1
        data, error_dict = shop.get_data(real_page)
        total_count -= len(data)/settings.PAGINATION
        request.session['data'] = (data, real_page, total_count)
    next = shop.is_data_finished(len(data), page + 1 - total_count)
    data = data[settings.PAGINATION * (page-total_count):settings.PAGINATION*(page+1-total_count)]
    if len(data) < settings.PAGINATION and next:
        real_page += 1
        new_data, error_dict = shop.get_data(real_page)
        if error_dict:
            return HttpResponse(simplejson.dumps({'response': error_dict, 'result': 'error'}))
        data = data + new_data[:settings.PAGINATION - len(data)]
        request.session['data'] = (new_data, real_page, page)
    if next:
        next += page
    previous = max(page - 1, 0)
    response = render_to_string('partial/products_table.html',
                                {'data': data, 'sync_type': shop.sync_type,
                                 'next': next, 'previous': previous, 'page': page,
                                 'start_index': page * settings.PAGINATION})
    return HttpResponse(simplejson.dumps({'response': unicode(response), 'result': 'success'}))


@require_GET
def save_csv(request):
    shop = request.session.get('shop')
    # Bots don't have variable stored, do not cause exception
    if not shop:
        # Try also api
        domain = request.GET.get('domain')
        key = request.GET.get('key')
        if domain and key:
            shop = Shop.objects.filter(domain__contains=domain, key=key, temp=False)
        if not shop:
            raise Http404
        else:
            shop = shop[0]
    data_full = []
    data = []
    page = 0
    # set explicitly to False since data could be already retrieved on the first page
    shop.api.finished = False
    while not shop.api.finished:
        data, error_dict = shop.get_data(page, 1000)
        if error_dict:
            return HttpResponse(simplejson.dumps({'response': error_dict, 'result': 'error'}))
        page += 1
    data_full.extend(data)

    if data_full:
        response = HttpResponse(mimetype='text/csv')
        writer = csv.writer(response)
        response['Content-Disposition'] = 'attachment; filename=data.csv'
        writer.writerow(['#' + shop.sync_type, 'quantity', 'price'])
        for i, res in enumerate(data_full):
            values = res[5]
            values = [values[b] for b, _ in UpdateProductValidator.ATTRS if values.get(b) is not None]
            if shop.sync_type == 'ID':
                values.insert(0, str(i + 1))
                writer.writerow(values)
            else:
                values.insert(0, res[2].encode('utf-8'))
                writer.writerow(values)

        return response
    raise Http404


@prepopulate(AddShopForm)
def add_shop(request, form):
    """
    :type form: AddShopForm
    """
    shop = form.save(commit=False)
    shop.user = request.user
    shop.status = 'red'
    shop.save()
    update_shop_status.delay(shop)
    return HttpResponse(simplejson.dumps({'response': shop.id, 'result': 'success'}))


def temp_shop_save(request):
    shop = request.session.get('shop')
    if shop:
        shop.temp = False
        shop.save()
        return HttpResponse(str(shop.id))
    raise Http404


@login_required
def shop_status(request, pk):
    shop = get_object_or_404(Shop, pk=pk, user=request.user)
    if request.method == 'GET':
        wait_for_shop_status(shop)
    elif request.method == 'POST':
        update_shop_status(shop)
    return HttpResponse(simplejson.dumps([shop.status, shop.error_status]))


@login_required
def shop_edit(request, pk):
    shop = get_object_or_404(Shop, pk=pk, user=request.user)
    form = EditShopForm(request.POST or None, instance=shop, request=request)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return HttpResponse(simplejson.dumps({'response': shop.id, 'result': 'success'}))
        else:
            response = {}
            for k, v in form.errors.items():
                response[k] = v
            return HttpResponse(simplejson.dumps({'response': response, 'result': 'error'}))
    return direct_to_template(request, template="partial/shop_edit.html",
                              extra_context={'form': form, 'shop': shop})


@login_required
def shop_delete(request, pk):
    shop = get_object_or_404(Shop, pk=pk, user=request.user)
    if request.method == 'POST':
        shop.delete()
    return HttpResponse("ok")


@require_GET
@login_required
def update_shops(request):
    ShopFormSet = modelformset_factory(Shop, fields=('title', 'domain', 'sync_type', 'key'), extra=0)
    formset = ShopFormSet(queryset=Shop.objects.filter(user=request.user))
    return direct_to_template(request, "partial/shops_formset.html", {"formset": formset})


class MainView(ListView):
    template_name = "main.html"
    context_object_name = "shop_list"

    def get_queryset(self):
        return Shop.objects.filter(user=self.request.user, temp=False)

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(MainView, self).get_context_data(**kwargs)

        context['form'] = LoadDataForm(error_class=DivErrorList, request=self.request)
        context['add_form'] = AddShopForm()
        ShopFormSet = modelformset_factory(Shop, fields=('title', 'domain', 'sync_type', 'key'), extra=0)
        formset = ShopFormSet(queryset=context['shop_list'])
        context['formset'] = formset
        return context

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(MainView, self).dispatch(*args, **kwargs)


def load_shop(request, pk=None):
    if pk:
        shop = get_object_or_404(Shop, pk=pk, user=request.user)
        # TODO: update last access time so form can automatically select last shop
        form = LoadDataForm(error_class=DivErrorList, initial=shop.get_initial(), request=request)
    else:
        form = LoadDataForm(error_class=DivErrorList, request=request)
    return direct_to_template(request, 'partial/load_form.html', extra_context={'form': form})


@csrf_exempt
@require_POST
def module_activate(request):
    import socket
    from users.models import Profile
    from presta.forms import clean_domain
    from presta.db_logging import log_user_action
    form = ActivationForm(request.POST)
    if form.is_valid():
        # Check that request goes from the valid domain
        ip_addr = request.META['REMOTE_ADDR']
        domain_name = clean_domain(form.cleaned_data['domain']).split(':')[0]
        try:
            if ip_addr != socket.gethostbyname(domain_name):
                log_user_action.delay(form.cleaned_data['domain'], "Register IP mismatch", str(ip_addr), "")
                #return HttpResponseForbidden()
        except socket.error:
            log_user_action.delay(form.cleaned_data['domain'], "Socket Error",
                "Socket error on module activate", "")

        user, created = Profile.objects.get_or_create(email=form.cleaned_data['email'])
        if created:
            user.set_password(form.cleaned_data['password'])
            user.save()
        shop, created = Shop.objects.get_or_create(domain=form.cleaned_data['domain'], user=user,
                                                   defaults={'key': form.cleaned_data['key']})

        # If by some reason shop was already created as temp, make it not temp
        if not created and shop.temp:
            shop.temp = False
        _, error_dict = shop.get_data()
        if not error_dict:
            shop.set_ok()
        elif PrestaError.rewrite_disabled(error_dict):
            shop.set_alarm(PrestaError.REGEN_HTACCESS)
        else:
            shop.set_alarm(error_dict.values()[0])

        log_user_action.delay(form.cleaned_data['domain'], "Register Success", "", "")
        return HttpResponse("ok")
    raise Http404
