from datetime import datetime, date
from celery.task import periodic_task
from celery.schedules import crontab
from django.contrib.sessions.models import Session
from users.models import Profile


@periodic_task(ignore_result=True, run_every=crontab(hour=0, minute=0))
def clean_sessions():
    Session.objects.filter(expire_date__lt=datetime.now()).delete()


@periodic_task(ignore_result=True, run_every=crontab(hour=0, minute=0))
def update_subscriptions():
    from presta.models import Shop
    Shop.objects.filter(user__plan_expiry__lte=date.today()).update(is_schedule_enabled=False)
    Profile.objects.filter(plan_expiry__lte=date.today())\
        .update(plan=Profile.PLAN_FREE, plan_expiry=None)
