from django import forms
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _


class CustomSelectWidget(forms.Select):
    def render(self, name, value, attrs=None, choices=()):
        human_value = ''
        if not value:
            human_value = self.choices[0][1]
        else:
            for choice_key, human_value in self.choices:
                if value==choice_key:
                    break
        output = '<span class="custom-select"><span class="custom-select-inner">'+\
                  force_unicode(human_value)+'</span>'
        output += super(CustomSelectWidget, self).render(name, value, attrs, choices)
        output += '</span>'
        return mark_safe(output)


class TogglePasswordInput(forms.PasswordInput):
    # TODO: put to lib
    """Widget for password field without duplication"""
    TEXT = 1
    PASSWORD = 2

    def render(self, name, value, attrs=None):
        if not attrs.has_key('class'):
            attrs['class'] = name
        attrs_text = attrs.copy()
        attrs_pass = attrs.copy()

        # render name only for visible element
        name_pass, name_text = name, ''

        # disable autocomplete for text
        attrs_text['autocomplete'] = 'off'

        # set either text or password fields to hidden
        temp_attrs = attrs_text
        if not self.attrs.has_key('default') or self.attrs['default'] == TogglePasswordInput.TEXT:
            temp_attrs = attrs_pass
            name_text, name_pass = name_pass, name_text
        # remove id so we don't get two field with same ids
        del temp_attrs['id']
        temp_attrs['style'] = 'display:none;'

        output = forms.TextInput().render(name_text, value, attrs_text)
        output += forms.PasswordInput.render(self, name_pass, value, attrs_pass)
        output += '<a title="'+_('show/hide password')+'" data-target-class="'+attrs['class']+'" class="toggle-password" href="#"></a>'
        return mark_safe(output)
