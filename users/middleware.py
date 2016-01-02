# The code in this file mimics the code in
# django.contrib.auth.middleware.AuthenticationMiddleware,
# with a small enhancement for anonymous users
# Some explanation about internals:
# http://stackoverflow.com/questions/5644527/how-does-the-django-lazyuser-code-work
# http://jacobian.org/writing/django-internals-authen/

from django.contrib.auth import get_user
from presta.utils.shop_utils import add_guest_data

from users.models import Profile

class LazyUser(object):
    """
        Descriptor-class
        http://habrahabr.ru/blogs/python/122082/
    """
    def __get__(self, request, obj_type=None):
        if not hasattr(request, '_cached_user'):
            request._cached_user = get_user(request)
            if request._cached_user.is_anonymous():
                try:
                    assert request.session.session_key
                    request._cached_user = Profile.objects.get(session__session_key=request.session.session_key)
                except (Profile.DoesNotExist, AssertionError):
                    request._cached_user = add_guest_data(request.session)
                    # We need to manually set flag to store session because we didn't modify it
                    # and we didn't "authenticated" our guest user
                    request.session.modified = True
        return request._cached_user

class AuthenticationMiddleware(object):
    """ Authentication middleware that returns GuestProfile for not authenticated users """
    def process_request(self, request):
        assert hasattr(request, 'session'), "The Django authentication middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."
        request.__class__.user = LazyUser()
        return None
