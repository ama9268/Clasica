#!/bin/bash
set -e

if [ "$SERVICE" = "worker" ]; then
    exec celery -A clasica_project worker -l info
else
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    exec daphne -b 0.0.0.0 -p 8000 clasica_project.asgi:application
fi
