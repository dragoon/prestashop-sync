#!/usr/bin/env python
import os
import sys

proj_dir = os.path.abspath(os.path.dirname(__file__))
external_dir = os.path.join(proj_dir, 'external')
sys.path.insert(0, external_dir)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
