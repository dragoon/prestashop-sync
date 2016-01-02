import hashlib
from random import random
from django.contrib.auth.decorators import user_passes_test


def generate_activation_key(username):
    """
    Generate random activation key
    :rtype: str
    """
    salt = hashlib.sha1(str(random())).hexdigest()[:5]
    activation_key = hashlib.sha1(salt + username).hexdigest()
    return activation_key


def not_guest_required(function=None):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: not u.is_guest(),
        # TODO: make lazy with new django
        # https://code.djangoproject.com/ticket/5925
        login_url='/login/',
    )
    if function:
        return actual_decorator(function)
    return actual_decorator
