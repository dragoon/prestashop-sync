#!/usr/bin/env python

import os
import subprocess

def check_celery():
    pid = open('/home/dragoon/celery/celery.pid').read().strip()
    try:
        os.kill(int(pid), 0)
    except:
        os.unlink('/home/dragoon/celery/celery.pid')
        return False
    return True

if not os.path.exists('/home/dragoon/celery/celery.pid') or not check_celery():
    print 'Celery not running. Starting...'
    subprocess.call("/home/dragoon/celery/celeryd start", shell=True)
