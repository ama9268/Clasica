import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clasica_project.settings.production")

app = Celery("clasica_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
