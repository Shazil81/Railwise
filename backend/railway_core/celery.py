import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "railway_core.settings")

app = Celery("railway_core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
