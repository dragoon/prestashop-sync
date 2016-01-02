from django.contrib.auth.backends import ModelBackend
from users.models import Profile

class LoginzaModelBackend(ModelBackend):
    """ Auth backend that returns Profile instead of User """

    def authenticate(self, provider=None, uid=None):
        """ Authenticate the user """
        if not provider or not uid:
            return None

        try:
            user = Profile.objects.get(provider=provider, uid=uid)
            if not user.has_usable_password():
                return user
            else:
                return None
        except Profile.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Profile.objects.get(pk=user_id)
        except Profile.DoesNotExist:
            return None

class EmailModelBackend(ModelBackend):
    """ Auth backend that returns Profile instead of User """

    def authenticate(self, email=None):
        """ Authenticate the user """
        if not email:
            return None

        try:
            user = Profile.objects.get(email=email)
            return user
        except Profile.DoesNotExist, Profile.MultipleObjectsReturned:
            return None

    def get_user(self, user_id):
        try:
            return Profile.objects.get(pk=user_id)
        except Profile.DoesNotExist:
            return None

class EmailPasswordBackend(ModelBackend):
    """ Auth backend that returns Profile instead of User """

    def authenticate(self, username=None, password=None):
        try:
            user = Profile.objects.get(email=username)
            if user.check_password(password):
                return user
        except Profile.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Profile.objects.get(pk=user_id)
        except Profile.DoesNotExist:
            return None
