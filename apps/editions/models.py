import logging
from django.db import models

logger = logging.getLogger(__name__)


class Edition(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_PUBLISHED = "results_published"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Abierta"),
        (STATUS_CLOSED, "Cerrada"),
        (STATUS_PUBLISHED, "Resultados publicados"),
    ]

    date = models.DateField(unique=True, db_index=True)
    name = models.CharField(max_length=200)
    route_gpx = models.FileField(upload_to="routes/gpx/", null=True, blank=True)
    route_geojson = models.JSONField(null=True, blank=True)
    route_distance_km = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Edición"
        verbose_name_plural = "Ediciones"
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.name} ({self.date})"

    @property
    def is_registration_open(self) -> bool:
        return self.status == self.STATUS_OPEN

    @property
    def results_published(self) -> bool:
        return self.status == self.STATUS_PUBLISHED


class EditionMedia(models.Model):
    TYPE_PHOTO = "photo"
    TYPE_VIDEO = "video"
    TYPE_CHOICES = [
        (TYPE_PHOTO, "Foto"),
        (TYPE_VIDEO, "Vídeo"),
    ]

    edition = models.ForeignKey(
        Edition, on_delete=models.CASCADE, related_name="media"
    )
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    # Fotos
    photo = models.ImageField(upload_to="editions/media/", null=True, blank=True)
    # Vídeos (URL de YouTube / Vimeo)
    video_url = models.URLField(blank=True)
    caption = models.CharField(max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Media"
        verbose_name_plural = "Media"
        ordering = ["order", "uploaded_at"]

    def __str__(self) -> str:
        return f"{self.get_media_type_display()} — {self.edition}"

    @property
    def embed_url(self) -> str:
        """Convierte URL de YouTube/Vimeo a URL embebible."""
        url = self.video_url
        if not url:
            return ""
        if "youtube.com/watch?v=" in url:
            vid = url.split("v=")[1].split("&")[0]
            return f"https://www.youtube.com/embed/{vid}"
        if "youtu.be/" in url:
            vid = url.split("youtu.be/")[1].split("?")[0]
            return f"https://www.youtube.com/embed/{vid}"
        if "vimeo.com/" in url:
            vid = url.split("vimeo.com/")[1].split("?")[0]
            return f"https://player.vimeo.com/video/{vid}"
        return url
