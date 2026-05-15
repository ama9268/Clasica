import logging
from django.contrib.gis.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class Participation(models.Model):
    user = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="participations",
        db_index=True,
    )
    edition = models.ForeignKey(
        "editions.Edition",
        on_delete=models.CASCADE,
        related_name="participations",
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inscripción"
        verbose_name_plural = "Inscripciones"
        unique_together = [("user", "edition")]
        ordering = ["registered_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.edition}"


class Activity(models.Model):
    SOURCE_MOBILE = "mobile"
    SOURCE_STRAVA = "strava"
    SOURCE_CHOICES = [
        (SOURCE_MOBILE, "App móvil"),
        (SOURCE_STRAVA, "Strava"),
    ]

    participation = models.OneToOneField(
        Participation,
        on_delete=models.CASCADE,
        related_name="activity",
    )
    elapsed_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_valid = models.BooleanField(default=False)
    validation_score = models.FloatField(null=True, blank=True)
    average_moving_speed = models.FloatField(null=True, blank=True)  # km/h, speed > 0 points only
    recorded_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MOBILE)
    strava_activity_id = models.BigIntegerField(null=True, blank=True, unique=True)

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"

    def __str__(self) -> str:
        valid = "✓" if self.is_valid else "✗"
        return f"{valid} {self.participation} ({self.elapsed_time_seconds}s)"

    @property
    def elapsed_formatted(self) -> str:
        if not self.elapsed_time_seconds:
            return "—"
        h, rem = divmod(self.elapsed_time_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
