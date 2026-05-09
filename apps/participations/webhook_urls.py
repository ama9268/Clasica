from django.urls import path
from . import webhook_views

urlpatterns = [
    path("strava/", webhook_views.strava_webhook, name="strava_webhook"),
]
