import logging
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class UserProfile(AbstractUser):
    full_name = models.CharField(max_length=200, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    club = models.CharField(max_length=150, blank=True)

    # Strava OAuth — nunca exponer en API ni serializer
    strava_athlete_id = models.BigIntegerField(null=True, blank=True, unique=True, db_index=True)
    strava_access_token = models.TextField(blank=True)
    strava_refresh_token = models.TextField(blank=True)
    strava_token_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"

    def __str__(self) -> str:
        return self.full_name or self.username

    @property
    def strava_connected(self) -> bool:
        return bool(self.strava_athlete_id and self.strava_refresh_token)

    @property
    def strava_token_expired(self) -> bool:
        if not self.strava_token_expires_at:
            return True
        from datetime import timedelta
        return self.strava_token_expires_at - timezone.now() < timedelta(minutes=5)
