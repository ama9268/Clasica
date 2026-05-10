import json
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
    participation = models.OneToOneField(
        Participation,
        on_delete=models.CASCADE,
        related_name="activity",
    )
    elapsed_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    track_geometry = models.LineStringField(srid=4326, null=True, blank=True)
    is_valid = models.BooleanField(default=False)
    validation_score = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

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

    @property
    def track_geojson(self) -> dict | None:
        if self.track_geometry:
            return json.loads(self.track_geometry.geojson)
        return None
