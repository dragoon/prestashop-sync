from django import forms
from django.utils.translation import ugettext_lazy as _

from tools.utils import send_email


class RequestForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # Raises exception if request is not supplied
        self.request = kwargs.pop('request')
        super(RequestForm, self).__init__(*args, **kwargs)


class ContactForm(RequestForm):
    from_email = forms.EmailField(label=_('Your email'))
    message = forms.CharField(widget=forms.Textarea, label=_('Message'))

    def __init__(self, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        if  not self.request.user.is_guest():
            del self.fields['from_email']

    def notify(self):
        if self.is_valid():
            data = {'message': self.cleaned_data['message'],
                    'email': self.cleaned_data.get('from_email') or self.request.user.email}
            send_email.delay("mail/feedback", data, "Feedback")
