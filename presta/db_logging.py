import inspect
from celery.task import task
from presta.models import UserActivity

@task(ignore_result=True)
def log_user_action(domain, action, data, errors):
    UserActivity.objects.create(domain=domain, action=action, data=data, errors=errors)

def whosdaddy():
    return inspect.stack()[2][3]
