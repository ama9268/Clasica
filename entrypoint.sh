#!/bin/bash
set -e

export DJANGO_SETTINGS_MODULE=clasica_project.settings.base

if [ "$SERVICE" = "worker" ]; then
    exec celery -A clasica_project worker --beat -l info
else
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    exec daphne -b 0.0.0.0 -p 8000 clasica_project.asgi:application
fi
