from datetime import datetime

from django import forms
from django.forms.formsets import BaseFormSet
from django.forms.util import ErrorList
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from presta.models import Shop
from presta.widgets import CustomSelectWidget, TogglePasswordInput
from tools.forms import RequestForm
from tools.url_tags import slugify2

class DivErrorList(ErrorList):
    # TODO: make lib
    """ ErrorList class used to display errors in divs, not ul """

    def __unicode__(self):
        if not self:
            return u''
        return mark_safe(''.join([u'<div class="error">%s</div>' % e for e in self]))


def clean_domain(domain):
    if domain.startswith('http://'):
        domain = domain[7:]
    elif domain.startswith('https://'):
        domain = domain[8:]
    if domain.endswith('/'):
        domain = domain[:-1]
    return domain


class AttrDict:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class CSVReader:
    """mixin class to use in forms"""

    @classmethod
    def read_file(cls, csv_file):
        """
        Reads CSV File to lines
        :param csv_file: CSV File to read
        :rtype: list
        """
        lines = []
        for chunk in csv_file.chunks():
            lines.append(chunk)
        lines = ''.join(lines).splitlines()
        # Strip empty lines
        lines = [line for line in lines if line.strip()]
        return lines


class CSVValidator():
    def __init__(self, lines):
        """
        Performs initial checks on csv file contents
        Saves lines and line_count variables.
        :param lines: lines of csv file
        :type lines: list
        """
        self.shop = None

        if lines:
            # Detect if user used semicolon and convert to comma
            if len(lines[0].split(';'))>1:
                lines = '\n'.join(lines)
                lines = lines.replace(';', ',')
                lines = lines.split('\n')
            # Ignore comments
            lines = [line for line in lines if not line.startswith('#')]

        self.lines = lines
        self.line_count = len(lines)
        self.warning = None

    def __iter__(self):
        for line in self.lines:
            yield line

    def __nonzero__(self):
        """
        Returns True if CSV File is valid, False otherwise
        :rtype: bool
        """
        return bool(self.lines)


class ValidateError(StandardError):
    pass


class UpdateProductValidator(CSVValidator):
    ATTRS = (('quantity', lambda v: str(int(v))), ('base_price', lambda v: str(round(float(v), 2)) if v else v))

    def __init__(self, lines):
        """Additional validation"""
        CSVValidator.__init__(self, lines)
        # Add empty names that is used in generating response in upload_csv view
        self.names = []
        if self.lines:
            # Make sure we have all 2 required values for each line
            valid_lines = []
            for line in self.lines:
                if 2 <= len(line.split(',')) <= 3:
                    k, values = line.split(',', 1)
                    try:
                        values = self._get_values_dict(values)
                    except ValidateError, e:
                        self.warning = e.message
                        continue
                    valid_lines.append((k, values))
            self.lines = valid_lines
            self.line_count = len(self.lines)
            if not self.lines:
                self.warning = ugettext("All lines in the file are incorrect")

    def _get_values_dict(self, values):
        value_dict = {}
        for i, v in enumerate(values.split(',')):
            val_name, val_type = UpdateProductValidator.ATTRS[i]
            # Just check type, do not convert from string
            try:
                value_dict[val_name] = val_type(v)
            except ValueError:
                raise ValidateError(ugettext("File contains bad value: ") + v.decode('utf-8', 'ignore'))
            if v < 0:
                raise ValidateError(ugettext("File contains negative values"))
        return value_dict


class AddProductValidator(CSVValidator):

    def __init__(self, lines):
        """Additional validation"""
        CSVValidator.__init__(self, lines)
        new_lines = []
        if self.lines:
            # Make sure we have all 5 required values
            #TODO: add values validation
            for line in lines:
                values = line.split(',')
                if len(values)==5:
                    try:
                        values[0].decode('utf-8')
                    except UnicodeDecodeError:
                        continue
                    new_lines.append(line)
        self.lines = new_lines

    def get_form_repr(self):
        """
        :return: form representation of CSV file for use in add products view
        """
        forms = []
        lang_id = self.shop.api.default_lang
        categories = dict(self.shop.api.get_categories())
        for order, line in enumerate(self.lines):
            name, category, price, quantity, desc = line.split(',')

            #Select proper category
            if str(category) not in categories.keys():
                for k, v in categories.items():
                    if str(category).lower() == v.lower():
                        category = k
                        break

            form = AttrDict(cleaned_data={})
            form.cleaned_data = dict(langs = [dict(id=lang_id, name=name,
                                                      link_rewrite=slugify2(name),
                                                      product_desc=desc,
                                                      product_desc_short=desc)],
                                   quantity = quantity, price= price,
                                   categories = [category], order=order)
            forms.append(form)
        return forms

    @property
    def names(self):
        """
        Used to return file names to show on product images upload.
        :return: list of product names
        :rtype: list
        """
        return [line.split(',')[0] for line in self.lines]



class LoadDataBaseForm(RequestForm):
    """Base form for product quantity update"""
    domain = forms.URLField(max_length=255, label=_("Shop URL"),
                            help_text=_('Prestashop url, like www.yourshop.com'),
                            widget=forms.TextInput(attrs={'required':'1'}))
    sync_type = forms.ChoiceField(label=_("Sync type"), choices=Shop.SYNC_TYPE,
         help_text=_('Data synchronization type.<br/> Use<b>internal ids</b> of this site OR<br/>'
                     'other unique ids of your shop (like <b>EAN13</b>)'),
         widget=CustomSelectWidget)
    key = forms.CharField(max_length=255, label="Shop secret key",
                          widget=TogglePasswordInput(attrs={'default': TogglePasswordInput.TEXT}))

    def __init__(self, *args, **kwargs):
        super(LoadDataBaseForm, self).__init__(*args, **kwargs)
        self.is_demo = False
        # Populate form with last used shop if it is not bound
        if not self.is_bound and not kwargs.get('initial'):
            if self.request.user.shop_set.count():
                last_used_shop = self.request.user.shop_set.latest('last_update_time')
                initial = last_used_shop.get_initial()
                self.initial = initial
                self.is_demo = last_used_shop.is_demo()

    def clean_domain(self):
        return clean_domain(self.cleaned_data['domain'])

    def get_shop(self, force=False):
        cleaned_data = self.cleaned_data
        domain = cleaned_data.get('domain')
        sync_type = cleaned_data.get('sync_type')
        key = cleaned_data.get('key')
        shop = self.request.session.get('shop')
        if force or not shop:
            try:
                shop = Shop.objects.get(domain=domain, temp=False, user = self.request.user)
                shop.last_update_time = datetime.now()
                shop.save()
                # Assign new sync type but do not save
                shop.sync_type = sync_type
            except Shop.DoesNotExist:
                shop , created = \
                Shop.objects.get_or_create(user=self.request.user, temp=True,
                                           defaults = dict(domain=domain, sync_type=sync_type,
                                           key=key, status='green'))
                if not created:
                    if shop.domain!=domain or shop.sync_type!=sync_type or shop.key!=key:
                        shop.domain = domain
                        shop.sync_type = sync_type
                        shop.key = key
                        shop.save()
        return shop

    def is_demo_form(self):
        return self.is_demo


class LoadDataForm(LoadDataBaseForm, CSVReader):
    """Form for bulk-product quantity update through csv file"""
    CSV_FILE_NAME = 'csv_update_products_file'

    csv_file = forms.FileField(label=_('CSV Update File'), required=False,
                               help_text=_('File in comma-separated format like:<br/><pre>&lt;ID_PRODUCT&gt;,&lt;QUANTITY&gt;\n'
                                           '...</pre> Where &lt;ID_PRODUCT&gt; values is the values<br/>you receive after load data operation.'),
                               widget=forms.FileInput(attrs={'required':'1', 'size': '24'}))

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            return LoadDataForm.validate_csv_file(csv_file)
        csv_file = self.request.session.get(LoadDataForm.CSV_FILE_NAME)
        if not csv_file:
            raise forms.ValidationError(_("This field is required."))
        return csv_file

    @classmethod
    def validate_csv_file(cls, csv_file):
        return UpdateProductValidator(cls.read_file(csv_file))


class LoadDataSingleForm(LoadDataBaseForm):
    """Form for single-product quantity update"""

    def get_data(self, request):
        ids = request.POST.getlist('id[]')
        id_attrs = request.POST.getlist('id_attribute[]')
        quantities = request.POST.getlist('quantity[]')

        data_list = [(id, id_attribute, {'quantity': quantity})
                    for id, id_attribute, quantity in zip(ids, id_attrs, quantities)]
        return data_list


class AddShopForm(forms.ModelForm):
    domain = forms.URLField(label=_("Shop URL"))
    sync_type = forms.ChoiceField(widget=CustomSelectWidget, choices=Shop.SYNC_TYPE)
    class Meta:
        model = Shop
        fields = ('domain', 'sync_type', 'key')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(AddShopForm, self).__init__(*args, **kwargs)

    def clean_domain(self):
        return clean_domain(self.cleaned_data['domain'])

    def validate_unique_domain(self, cleaned_data):
        """Check unique user-domain ourselves because we don't have 'user' field in the form"""
        if self._meta.model.objects.filter(user=self.request.user, domain=cleaned_data.get('domain')).exists():
            self._errors["domain"] = self.error_class([ugettext('Shop with this name already exists')])
            del cleaned_data["domain"]

    def clean(self):
        """Override default to include user field in validation"""
        cleaned_data = super(AddShopForm, self).clean()
        self.validate_unique_domain(cleaned_data)
        return cleaned_data


class EditShopForm(AddShopForm):
    is_schedule_enabled = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=False,
                                             label=_('Scheduled Updates'))
    interval = forms.ChoiceField(widget=CustomSelectWidget, choices=Shop.INVERVALS)
    class Meta:
        model = Shop
        fields = ('title', 'domain', 'sync_type', 'key', 'is_schedule_enabled', 'location', 'interval')

    @property
    def is_enable_allowed(self):
        """
        :return: True if user is paid, False otherwise
        :rtype: bool
        """
        return self.request.user.is_paid()

    def validate_unique_domain(self, cleaned_data):
        """In edit form we need to check if more than will exist if we save"""
        if self.instance:
            if self._meta.model.objects.exclude(id=self.instance.id).\
                filter(user=self.request.user, domain=cleaned_data.get('domain')).exists():
                self._errors["domain"] = self.error_class([ugettext('Shop with this name already exists')])
                del cleaned_data["domain"]

    def clean(self):
        data = super(EditShopForm, self).clean()
        if data.get('is_schedule_enabled'):
            if not data.get('location'):
                self._errors['location'] = self.error_class(['This field is required.'])
            if not self.is_enable_allowed:
                # TODO: make test to make sure it works
                data['is_schedule_enabled'] = False
        else:
            data['interval'] = Shop.INVERVALS[0][0]
            data['location'] = self.instance.location
            # TODO: sometime interval is not in errors, why? may be when other errors present?
            if 'interval' in self._errors:
                del self._errors['interval']
        return data


class AddProductsShopForm(forms.Form, CSVReader):
    CSV_FILE_NAME = 'csv_add_products_file'

    name = forms.CharField(max_length=255, label=_("Product Name"),
                           widget=forms.TextInput(attrs={'required':'1'}))
    category = forms.ChoiceField(label=_("Category"),choices=(), widget=CustomSelectWidget)
    price = forms.IntegerField(label=_("Price"), widget=forms.TextInput(attrs={'required':'1'}))
    quantity = forms.IntegerField(label=_("Quantity"),
                                  widget=forms.TextInput(attrs={'required':'1'}))
    description = forms.CharField(label=_("Description"), widget=forms.Textarea, required=False)
    order = forms.IntegerField(widget=forms.HiddenInput, initial=0)

    def __init__(self, *args, **kwargs):
        self.shop = kwargs.pop('shop')
        super(AddProductsShopForm, self).__init__(*args, **kwargs)
        self.fields['category'].choices = self.shop.api.get_categories()

    def clean(self):
        lang_id = self.shop.api.default_lang
        data = self.cleaned_data

        if data.get('name') and data.get('category'):
            name = data.pop('name')
            # Only one language for now
            data['langs'] = [{'id':lang_id, 'name':name, 'link_rewrite':slugify2(name),
                              'product_desc':data.get('description'),
                              'product_desc_short':data.get('description')}]
            data['categories'] = [data.pop('category')]
        return data

    @classmethod
    def validate_csv_file(cls, csv_file):
        return AddProductValidator(cls.read_file(csv_file))


class AddProductsShopBaseFormSet(BaseFormSet):
     def __init__(self, *args, **kwargs):
         super(AddProductsShopBaseFormSet, self).__init__(*args, **kwargs)
         self.csv_file = None

     def clean(self):
         """
         Check session attribute to find if CSV add file present in session.
         If present, replace all forms with data from CSV file.
         """
         if self.csv_file:
             #TODO: add category validation here
             self.forms = self.csv_file.get_form_repr()
             self._errors = [0]*self.total_form_count()
             return
         if any(self.errors):
             return

class ActivationForm(forms.Form):
    domain = forms.CharField(max_length=255)
    key = forms.CharField(max_length=32, min_length=32)
    email = forms.EmailField()
    password = forms.CharField()

    def clean_domain(self):
        return clean_domain(self.cleaned_data['domain'])
