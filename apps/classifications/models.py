import logging
from datetime import date
from django.db import models

logger = logging.getLogger(__name__)

CATEGORY_OPEN = "open"
CATEGORY_M40 = "m40"
CATEGORY_M50 = "m50"
CATEGORY_M60 = "m60"
CATEGORY_CHOICES = [
    (CATEGORY_OPEN, "Open / Elite"),
    (CATEGORY_M40, "Master 40"),
    (CATEGORY_M50, "Master 50"),
    (CATEGORY_M60, "Master 60+"),
]


def get_category(birth_date: date, edition_date: date) -> str:
    age = (edition_date - birth_date).days // 365
    if age >= 60:
        return CATEGORY_M60
    if age >= 50:
        return CATEGORY_M50
    if age >= 40:
        return CATEGORY_M40
    return CATEGORY_OPEN


class Classification(models.Model):
    participation = models.OneToOneField(
        "participations.Participation",
        on_delete=models.CASCADE,
        related_name="classification",
    )
    time_seconds = models.PositiveIntegerField(null=True, blank=True)
    category = models.CharField(
        max_length=10, choices=CATEGORY_CHOICES, default=CATEGORY_OPEN, db_index=True
    )
    position_overall = models.PositiveIntegerField(null=True, blank=True)
    position_category = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Clasificación"
        verbose_name_plural = "Clasificaciones"
        ordering = ["position_overall"]

    def __str__(self) -> str:
        return f"#{self.position_overall} {self.participation.user} [{self.category}]"

    @property
    def time_formatted(self) -> str:
        if not self.time_seconds:
            return "—"
        h, rem = divmod(self.time_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
