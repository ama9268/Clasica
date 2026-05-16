import pytest
from django.contrib.gis.geos import LineString

from apps.participations.tasks import validate_track


@pytest.mark.django_db
class TestValidateTrack:
    """Integración real con PostGIS — requiere PostgreSQL + PostGIS."""

    def _make_noisy_track(self, base_coords, noise=0.0001):
        """Desplaza los puntos un pequeño ruido (~10 m) manteniendo el track cerca de la ruta."""
        import random
        random.seed(42)
        noisy = [
            (lon + random.uniform(-noise, noise), lat + random.uniform(-noise, noise))
            for lon, lat in base_coords
        ]
        return LineString(noisy, srid=4326)

    def _make_deviated_track(self, base_coords, offset=0.05):
        """Desplaza los puntos ~5 km lateralmente — track inválido."""
        deviated = [(lon + offset, lat + offset) for lon, lat in base_coords]
        return LineString(deviated, srid=4326)

    def test_valid_track_perfect_match(self, route_geom):
        """Track idéntico a la ruta oficial → score ≈ 1.0, is_valid=True."""
        score, is_valid = validate_track(route_geom, route_geom)
        assert is_valid is True
        assert score >= 0.80

    def test_valid_track_with_noise(self, route_geom):
        """Track con ruido de ~10 m → sigue siendo válido."""
        base_coords = list(route_geom.coords)
        noisy_track = self._make_noisy_track(base_coords, noise=0.0001)
        score, is_valid = validate_track(route_geom, noisy_track)
        assert is_valid is True
        assert score >= 0.80

    def test_invalid_track_deviation(self, route_geom):
        """Track desviado ~5 km → inválido."""
        base_coords = list(route_geom.coords)
        deviated_track = self._make_deviated_track(base_coords, offset=0.05)
        score, is_valid = validate_track(route_geom, deviated_track)
        assert is_valid is False
        assert score < 0.80

    def test_empty_edition_geometry(self, route_geom):
        """Sin geometría de edición → (0.0, False) sin excepción."""
        user_track = LineString([(-6.0, 38.0), (-6.1, 38.1)], srid=4326)
        score, is_valid = validate_track(None, user_track)
        assert score == 0.0
        assert is_valid is False

    def test_empty_user_geometry(self, route_geom):
        """Sin geometría del participante → (0.0, False) sin excepción."""
        score, is_valid = validate_track(route_geom, None)
        assert score == 0.0
        assert is_valid is False
