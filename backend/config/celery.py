import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# This reads all CELERY_ prefixed settings from settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Automatically find tasks.py in all INSTALLED_APPS
app.autodiscover_tasks()