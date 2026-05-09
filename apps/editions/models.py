import logging
import json
from django.contrib.gis.db import models
from django.utils import timezone
from datetime import time

logger = logging.getLogger(__name__)


class RouteVariant(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    route_gpx = models.FileField(upload_to="variants/gpx/")
    route_geometry = models.LineStringField(srid=4326, null=True, blank=True, spatial_index=True)
    route_distance_km = models.FloatField(null=True, blank=True)
    elevation_profile = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.route_gpx:
            from .services.gpx_parser import parse_gpx_file
            try:
                geom, dist, profile = parse_gpx_file(self.route_gpx.open())
                if geom:
                    self.route_geometry = geom
                    self.route_distance_km = dist
                    self.elevation_profile = profile
            except Exception as e:
                logger.error(f"Error parseando GPX en Variant: {e}")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Variante de Ruta"
        verbose_name_plural = "Variantes de Ruta"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def route_geojson(self) -> str | None:
        if self.route_geometry:
            return self.route_geometry.geojson
        return None


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
    start_time = models.TimeField(default=time(16, 30), verbose_name="Hora de salida")
    route_variant = models.ForeignKey(RouteVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="editions")
    route_gpx = models.FileField(upload_to="routes/gpx/", null=True, blank=True)
    route_geometry = models.LineStringField(srid=4326, null=True, blank=True, spatial_index=True)
    route_distance_km = models.FloatField(null=True, blank=True)
    elevation_profile = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Solo procesamos si hay un archivo GPX directo en la edición
        if self.route_gpx:
            from .services.gpx_parser import parse_gpx_file
            try:
                geom, dist, profile = parse_gpx_file(self.route_gpx.open())
                if geom:
                    self.route_geometry = geom
                    self.route_distance_km = dist
                    self.elevation_profile = profile
            except Exception as e:
                logger.error(f"Error parseando GPX en Edition: {e}")
        super().save(*args, **kwargs)

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

    @property
    def is_live(self) -> bool:
        """Determina si el seguimiento en directo debe estar activo."""
        now = timezone.localtime(timezone.now())
        if now.date() != self.date or self.results_published:
            return False
        return self.start_time <= now.time() <= time(21, 30)

    @property
    def has_started(self) -> bool:
        """Indica si la edición ya ha comenzado o pasado (basado en fecha y hora)."""
        now = timezone.localtime(timezone.now())
        if now.date() > self.date:
            return True
        if now.date() == self.date:
            return now.time() >= self.start_time
        return False

    @property
    def route_geom(self):
        """Retorna el objeto GEOSGeometry (nativa) para el serializador GIS."""
        return self.route_geometry or (self.route_variant.route_geometry if self.route_variant else None)

    @property
    def route_geojson(self) -> str | None:
        if self.route_geometry:
            return self.route_geometry.geojson
        if self.route_variant and self.route_variant.route_geometry:
            return self.route_variant.route_geometry.geojson
        return None

    @property
    def get_elevation_profile(self) -> list | None:
        if self.elevation_profile is not None:
            return self.elevation_profile
        if self.route_variant and self.route_variant.elevation_profile is not None:
            return self.route_variant.elevation_profile
        return None

    @property
    def get_route_distance(self) -> float | None:
        if self.route_distance_km is not None:
            return self.route_distance_km
        if self.route_variant:
            return self.route_variant.route_distance_km
        return None

    @property
    def total_elevation_gain(self) -> int:
        profile = self.get_elevation_profile
        if not profile:
            return 0
        gain = 0
        prev_alt = None
        for p in profile:
            # Soporta tanto formato lista [dist, alt] como dict {"dist": x, "alt": y}
            alt = p.get('alt', 0) if isinstance(p, dict) else (p[1] if len(p) > 1 else 0)
            if prev_alt is not None and alt > prev_alt:
                gain += (alt - prev_alt)
            prev_alt = alt
        return int(gain)


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
