#!/usr/bin/env python
import os
import sys

# Configurar Django
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
sys.path.insert(0, project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proprint3d_project.settings')

import django
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    args = sys.argv[1:]
    call_command('unify_orders_by_client', *args)
