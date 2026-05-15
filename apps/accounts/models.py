from django.contrib.auth.models import AbstractUser
from django.db import models


class UserProfile(AbstractUser):
    full_name = models.CharField(max_length=200, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    club = models.CharField(max_length=150, blank=True)

    # Strava OAuth
    strava_athlete_id = models.BigIntegerField(null=True, blank=True, unique=True)
    strava_access_token = models.CharField(max_length=255, blank=True)
    strava_refresh_token = models.CharField(max_length=255, blank=True)
    strava_token_expires_at = models.DateTimeField(null=True, blank=True)

    @property
    def strava_connected(self) -> bool:
        return bool(self.strava_athlete_id and self.strava_refresh_token)

    def save(self, *args, **kwargs):
        if self.photo and not self.photo._committed:
            from clasica_project.image_utils import optimize_image
            self.photo = optimize_image(self.photo)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"

    def __str__(self) -> str:
        return self.full_name or self.username
