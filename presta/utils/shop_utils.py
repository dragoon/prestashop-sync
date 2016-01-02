from time import sleep
from celery.task import task

from django.conf import settings
from django.contrib.sessions.models import Session

from presta.forms import AddShopForm
from presta.models import Shop
from users.models import Profile


@task(ignore_result=True)
def update_shop_status(shop):
    _, errors = shop.get_data()
    if errors:
        shop.set_alarm()
        k, v = errors.items()[0]
        try:
            k = AddShopForm.base_fields[k].label
        except IndexError:
            pass
        shop.error_status = k + ": " + v
    else:
        shop.set_ok()
    shop.save()


def wait_for_shop_status(shop):
    k = 10
    while k and not shop.is_ok() and not shop.error_status:
        sleep(1)
        k -= 1


def transfer_objects(old_user, new_user):
    Shop.objects.filter(user=old_user).update(user=new_user)


def add_guest_data(session):
    session.save()
    session = Session.objects.get(session_key=session.session_key)
    user, created = Profile.objects.get_or_create(session=session, email=settings.GUEST_EMAIL)
    if created:
        user.set_unusable_password()
        user.save()
        initial = settings.DEMO_SHOP_FULL
        Shop.objects.create(user=user, **initial)
    return user
