import logging
from django.db import models
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


class StravaActivity(models.Model):
    participation = models.OneToOneField(
        Participation,
        on_delete=models.CASCADE,
        related_name="strava_activity",
    )
    strava_activity_id = models.BigIntegerField(unique=True, db_index=True)
    elapsed_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    # Track GPS como GeoJSON: {"type":"LineString","coordinates":[[lon,lat],...]}
    track_geojson = models.JSONField(null=True, blank=True)
    is_valid = models.BooleanField(default=False)
    validation_score = models.FloatField(null=True, blank=True)
    imported_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Actividad Strava"
        verbose_name_plural = "Actividades Strava"

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
