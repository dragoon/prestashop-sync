from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import ugettext_lazy as _
from presta.widgets import TogglePasswordInput, CustomSelectWidget

from tools.forms import RequestForm
from users.models import Profile


class SetPasswordForm(forms.Form):
    #TODO: put to lib
    """(Re)setting password for a user"""

    new_password = forms.CharField(label=_("New password"),
                                    widget=TogglePasswordInput(attrs={'default': TogglePasswordInput.PASSWORD}))

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(SetPasswordForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        self.user.set_password(self.cleaned_data['new_password'])
        if commit:
            self.user.save()
        return self.user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(label=_("Email"), max_length=255)
    password = forms.CharField(label=_("Password"),
                               widget=TogglePasswordInput(attrs={'default': TogglePasswordInput.PASSWORD}))


class RegisterForm(forms.ModelForm):
    password = forms.CharField(label=_("Password"),
                               widget=TogglePasswordInput(attrs={'default': TogglePasswordInput.TEXT}))
    plan = forms.ChoiceField(label=_("Plan"), choices=Profile.PLAN_CHOICES.items(), widget=CustomSelectWidget)

    class Meta:
        model = Profile
        fields = ("email", "password", "plan")

    def clean_email(self):
        email = self.cleaned_data["email"]
        try:
            Profile.objects.get(email=email)
        except Profile.DoesNotExist:
            return email
        raise forms.ValidationError(_("A user with this email already exists"))

    def save(self, commit=True):
        user = super(RegisterForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class RequestEmailForm(RequestForm):
    email = forms.EmailField()


class DeleteUserForm(forms.Form):
    pass

