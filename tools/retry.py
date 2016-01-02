import time
from functools import wraps


def retry(exception=Exception, attempts=3, delay=3):
    """attempts - number of attempts to retry"""
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(attempts):
                try:
                    return func(*args, **kwargs)
                except exception, e:
                    # Check type because we don't want to catch HTTPError in case of URLError
                    if type(e) != type(exception):
                        break
                    time.sleep(delay)
            #if no success after tries OR not the right exception type, raise last exception
            raise
        return wrapper
    return inner
