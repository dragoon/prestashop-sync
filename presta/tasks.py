from datetime import datetime, timedelta
import urllib2
from celery.task import periodic_task, task
from celery.schedules import crontab
from celery.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from django.utils.translation import ugettext as _

from presta.models import Shop, UpdateStatus, UserActivity
from tools.utils import send_email, send_html_email


@periodic_task(ignore_result=True, run_every=crontab(minute="0"))
def update_shops_data():
    from presta.db_logging import log_user_action
    from presta.forms import UpdateProductValidator
    shops = Shop.objects.filter(is_schedule_enabled=True)
    #shops = Shop.objects.filter(schedule__is_null=False).select_related('schedule')
    for shop in shops:
        update_index = shop.interval / 60 - 1
        if shop.update_index == update_index:
            try:
                csv_file = urllib2.urlopen(shop.location).read()
            except urllib2.URLError:
                log_user_action.delay(shop.domain, "CSV Update location error",
                                      str(shop.location), "Error")
                continue
            lines = UpdateProductValidator(csv_file.splitlines())
            # TODO: proper language detection
            if shop.domain.endswith(u'.ru') or shop.domain.endswith(u'.ua'):
                language = 'ru'
            else:
                language = 'en'
            checked_update_presta_data_periodic.delay(shop, lines, language)
            shop.update_index = 0
        else:
            shop.update_index += 1
        # TODO: django 1.5 update only one field
        shop.save()


@periodic_task(ignore_result=True, run_every=crontab(minute="0", hour="0"))
def clean_old_activities():
    UserActivity.objects.filter(domain=settings.DEMO_SHOP['domain'],
                                date__lt=(datetime.now() - timedelta(days=1))).delete()


@task(ignore_result=True, time_limit=3600)
def checked_update_presta_data_periodic(shop, lines, language):
    user = shop.user
    # tracks if exception happened
    message = None
    try:
        result = shop.prepare_data_for_update(lines)
        if result['result'] == 'success':
            result_dict = shop.api.update_presta_data(result['response'])
            start_char = u'\u2713 '
            result_dict['language'] = language
            if result_dict['errors']:
                start_char = u'\u2717 '
                send_html_email.delay('mail/customers/update_report.html', result_dict,
                                      'Periodic update failure for {0}'.format(shop.domain))
            send_html_email.delay('mail/customers/update_report.html', result_dict,
                                  start_char + _('Periodic update report for %s') % shop.domain,
                                  email=[user.email])
        else:
            message = str(result['response'])
    except Exception, e:
        message = unicode(e)
    # notify
    if message is not None:
        send_email.delay('mail/feedback',
                         {'message': u'{0}:\n{1}'.format(unicode(shop.domain), message),
                          'email': user.email},
                         'Exception during periodic checked update')
        send_email.delay('mail/customers/csv_update_error.html',
                         {'language': language, 'message': unicode(message)},
                         _('Scheduled update failure'), email=[user.email])


def _checked_update_presta_data(shop, data_list, language):
    domain = shop.domain
    user = shop.user
    # TODO: this is something weird, it seems that update status is never updated after creation
    status, created = UpdateStatus.objects.get_or_create(domain=domain,
                                                         defaults={'update_status': 'wait'})
    try:
        result_dict = shop.api.update_presta_data(data_list)
        start_char = u'\u2713 '
        result_dict['language'] = language
        if result_dict['errors']:
            start_char = u'\u2717 '
            send_html_email.delay('mail/customers/update_report.html', result_dict,
                                  'Update failure for {0}'.format(shop.domain))
        send_html_email.delay('mail/customers/update_report.html', result_dict,
                              start_char + _('Update report for %s') % shop.domain,
                              email=[user.email])
    except SoftTimeLimitExceeded:
        # send email
        send_email.delay('mail/feedback', {'message': unicode(shop.domain), 'email': user.email},
                         'Time limit exceeded')
        send_email.delay('mail/customers/time_limit_exceeded.html', {'language': language},
                         _('Time limit exceeded'), email=[user.email])
    status.update_status = 'success'
    status.save()


def checked_update_presta_data_task(shop, *args, **kwargs):
    if shop.user.is_paid():
        checked_update_presta_data.delay(shop, *args, **kwargs)
    else:
        checked_update_presta_data_free.delay(shop, *args, **kwargs)


checked_update_presta_data_free = task(ignore_result=True,
                                       name="presta.tasks.checked_update_presta_data_free",
                                       soft_time_limit=300,
                                       time_limit=305)(_checked_update_presta_data)

checked_update_presta_data = task(ignore_result=True,
                                  name="presta.tasks.checked_update_presta_data",
                                  time_limit=3600)(_checked_update_presta_data)

