import pytest
from unittest.mock import patch
from datetime import date, time

from django.urls import reverse
from rest_framework.throttling import SimpleRateThrottle

from apps.editions.models import Edition
from apps.participations.models import Activity, Participation


VALID_TRACK_GEOJSON = {
    "type": "LineString",
    "coordinates": [[-6.00, 38.00], [-6.02, 38.02], [-6.04, 38.04]],
}


# ── RegisterAPIView ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRegisterAPIView:

    def test_register_success(self, api_client):
        resp = api_client.post("/api/v1/auth/register/", {
            "username": "nuevousuario",
            "email": "nuevo@test.com",
            "password": "ClaveSegura123",
            "full_name": "Nuevo Usuario",
        })
        assert resp.status_code == 201
        assert resp.data["username"] == "nuevousuario"

    def test_register_duplicate_username(self, api_client, user):
        resp = api_client.post("/api/v1/auth/register/", {
            "username": "ciclista1",  # ya existe (fixture user)
            "email": "otro@test.com",
            "password": "ClaveSegura123",
        })
        assert resp.status_code == 400


# ── EditionRegisterAPIView ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestEditionRegisterAPIView:

    def test_register_to_open_edition(self, auth_client, edition):
        resp = auth_client.post(f"/api/v1/editions/{edition.pk}/register/")
        assert resp.status_code == 200
        assert resp.data["registered"] is True
        assert resp.data["created"] is True

    def test_register_already_registered(self, auth_client, edition, participation):
        # participation fixture ya inscribió al user
        resp = auth_client.post(f"/api/v1/editions/{edition.pk}/register/")
        assert resp.status_code == 200
        assert resp.data["created"] is False
        assert Participation.objects.filter(user__username="ciclista1", edition=edition).count() == 1

    def test_register_to_closed_edition(self, auth_client, db):
        closed = Edition.objects.create(
            date=date(2025, 1, 10),
            name="Cerrada",
            start_time=time(16, 30),
            status=Edition.STATUS_CLOSED,
        )
        resp = auth_client.post(f"/api/v1/editions/{closed.pk}/register/")
        assert resp.status_code == 400

    def test_register_unauthenticated(self, api_client, edition):
        resp = api_client.post(f"/api/v1/editions/{edition.pk}/register/")
        assert resp.status_code in (401, 403)


# ── ActivityUploadAPIView ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestActivityUploadAPIView:

    def _payload(self, elapsed=3600):
        return {
            "elapsed_time_seconds": elapsed,
            "average_moving_speed": 28.5,
            "track_geojson": VALID_TRACK_GEOJSON,
        }

    @patch("apps.participations.tasks.validate_track", return_value=(0.95, True))
    def test_upload_valid_track(self, mock_vt, auth_client, edition, participation):
        resp = auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            self._payload(),
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["is_valid"] is True
        assert resp.data["validation_score"] == 0.95

        # Activity creada
        activity = Activity.objects.get(participation=participation)
        assert activity.is_valid is True
        assert activity.elapsed_time_seconds == 3600

        # Edición publicada automáticamente
        edition.refresh_from_db()
        assert edition.status == Edition.STATUS_PUBLISHED

    @patch("apps.participations.tasks.validate_track", return_value=(0.50, False))
    def test_upload_invalid_track(self, mock_vt, auth_client, edition, participation):
        resp = auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            self._payload(),
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["is_valid"] is False

        activity = Activity.objects.get(participation=participation)
        assert activity.is_valid is False

        # Edición no cambia de estado
        edition.refresh_from_db()
        assert edition.status == Edition.STATUS_OPEN

    def test_upload_not_registered(self, auth_client, edition):
        # No hay participation → el usuario no está inscrito
        resp = auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            self._payload(),
            format="json",
        )
        assert resp.status_code == 400

    def test_upload_missing_elapsed(self, auth_client, edition, participation):
        payload = {"track_geojson": VALID_TRACK_GEOJSON}
        resp = auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            payload,
            format="json",
        )
        assert resp.status_code == 400

    def test_upload_missing_track(self, auth_client, edition, participation):
        payload = {"elapsed_time_seconds": 3600}
        resp = auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            payload,
            format="json",
        )
        assert resp.status_code == 400

    def test_upload_bad_geojson(self, auth_client, edition, participation):
        payload = {
            "elapsed_time_seconds": 3600,
            "track_geojson": {"type": "Point", "coordinates": "invalid"},
        }
        resp = auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            payload,
            format="json",
        )
        assert resp.status_code == 400

    @patch("apps.participations.tasks.validate_track", return_value=(0.92, True))
    def test_upload_updates_existing_activity(self, mock_vt, auth_client, edition, participation):
        # Primer upload
        auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            self._payload(elapsed=4000),
            format="json",
        )
        # Segundo upload — debe actualizar, no duplicar
        auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            self._payload(elapsed=3500),
            format="json",
        )
        assert Activity.objects.filter(participation=participation).count() == 1
        activity = Activity.objects.get(participation=participation)
        assert activity.elapsed_time_seconds == 3500


# ── Throttling ───────────────────────────────────────────────────────────────

# Tasas mínimas para tests: 1 petición por período → la 2ª siempre es 429
LOW_THROTTLE_RATES = {
    "anon": "100/minute",
    "user": "100/minute",
    "login": "1/minute",
    "register": "1/minute",
    "activity_upload": "1/hour",
    "token_refresh": "100/minute",
    "webhook": "1/minute",
}


@pytest.mark.django_db
class TestThrottling:
    """
    DRF cachea THROTTLE_RATES como atributo de clase en import time.
    override_settings(REST_FRAMEWORK=...) no actualiza ese atributo,
    por eso parcheamos SimpleRateThrottle.THROTTLE_RATES directamente.
    """

    @patch.object(SimpleRateThrottle, "THROTTLE_RATES", LOW_THROTTLE_RATES)
    def test_register_throttled_after_limit(self, api_client):
        payload = {"username": "u1", "email": "u1@t.com", "password": "Clave123!"}
        api_client.post("/api/v1/auth/register/", payload)
        resp = api_client.post("/api/v1/auth/register/", {**payload, "username": "u2", "email": "u2@t.com"})
        assert resp.status_code == 429

    @patch.object(SimpleRateThrottle, "THROTTLE_RATES", LOW_THROTTLE_RATES)
    def test_login_throttled_after_limit(self, api_client, user):
        api_client.post("/api/v1/auth/login/", {"username": "ciclista1", "password": "testpass123"})
        resp = api_client.post("/api/v1/auth/login/", {"username": "ciclista1", "password": "testpass123"})
        assert resp.status_code == 429

    @patch.object(SimpleRateThrottle, "THROTTLE_RATES", LOW_THROTTLE_RATES)
    @patch("apps.participations.tasks.validate_track", return_value=(0.95, True))
    def test_activity_upload_throttled_after_limit(self, mock_vt, auth_client, edition, participation):
        payload = {
            "elapsed_time_seconds": 3600,
            "average_moving_speed": 28.5,
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
        }
        auth_client.post(f"/api/v1/editions/{edition.pk}/activity/", payload, format="json")
        resp = auth_client.post(f"/api/v1/editions/{edition.pk}/activity/", payload, format="json")
        assert resp.status_code == 429

    @patch.object(SimpleRateThrottle, "THROTTLE_RATES", LOW_THROTTLE_RATES)
    def test_throttle_response_has_retry_after_header(self, api_client):
        payload = {"username": "u1", "email": "u1@t.com", "password": "Clave123!"}
        api_client.post("/api/v1/auth/register/", payload)
        resp = api_client.post("/api/v1/auth/register/", {**payload, "username": "u2", "email": "u2@t.com"})
        assert resp.status_code == 429
        assert "Retry-After" in resp


# ── Validación de inputs (ActivityUploadSerializer) ──────────────────────────

@pytest.mark.django_db
class TestActivityUploadValidation:
    """Valida que el serializer rechaza inputs fuera de rango antes de llegar a PostGIS."""

    def _post(self, auth_client, edition, payload):
        return auth_client.post(
            f"/api/v1/editions/{edition.pk}/activity/",
            payload,
            format="json",
        )

    def test_elapsed_zero_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 0,
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
        })
        assert resp.status_code == 400
        assert "elapsed_time_seconds" in resp.data

    def test_elapsed_negative_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": -100,
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
        })
        assert resp.status_code == 400
        assert "elapsed_time_seconds" in resp.data

    def test_elapsed_too_large_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 99999,  # > 18 h (64800 s)
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
        })
        assert resp.status_code == 400
        assert "elapsed_time_seconds" in resp.data

    def test_speed_negative_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 3600,
            "average_moving_speed": -10.0,
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
        })
        assert resp.status_code == 400
        assert "average_moving_speed" in resp.data

    def test_speed_absurd_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 3600,
            "average_moving_speed": 999.0,  # > 120 km/h
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
        })
        assert resp.status_code == 400
        assert "average_moving_speed" in resp.data

    def test_track_not_linestring_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 3600,
            "track_geojson": {"type": "Point", "coordinates": [-6.0, 38.0]},
        })
        assert resp.status_code == 400

    def test_track_single_point_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 3600,
            "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0]]},
        })
        assert resp.status_code == 400

    def test_track_out_of_range_coords_rejected(self, auth_client, edition, participation):
        resp = self._post(auth_client, edition, {
            "elapsed_time_seconds": 3600,
            "track_geojson": {"type": "LineString", "coordinates": [[999.0, 38.0], [-6.1, 38.1]]},
        })
        assert resp.status_code == 400

    def test_speed_null_accepted(self, auth_client, edition, participation):
        """average_moving_speed es opcional — null es válido."""
        with patch("apps.participations.tasks.validate_track", return_value=(0.9, True)):
            resp = self._post(auth_client, edition, {
                "elapsed_time_seconds": 3600,
                "average_moving_speed": None,
                "track_geojson": {"type": "LineString", "coordinates": [[-6.0, 38.0], [-6.1, 38.1]]},
            })
        assert resp.status_code == 200


# ── Health Check ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthCheck:

    def test_health_returns_200(self, api_client):
        resp = api_client.get("/api/health/")
        assert resp.status_code == 200
        assert resp.data["status"] == "ok"

    def test_health_checks_database(self, api_client):
        resp = api_client.get("/api/health/")
        assert resp.data["database"] == "ok"

    def test_health_checks_cache(self, api_client):
        resp = api_client.get("/api/health/")
        assert resp.data["cache"] == "ok"

    def test_health_no_auth_required(self, api_client):
        """El endpoint es público — no necesita token."""
        resp = api_client.get("/api/health/")
        assert resp.status_code == 200


# ── N+1 queries ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNPlusOneQueries:

    def test_edition_list_fixed_queries(self, auth_client, django_assert_num_queries):
        """GET /editions/ debe usar una sola query independientemente del nº de ediciones."""
        from datetime import date, time
        from apps.editions.models import Edition, RouteVariant
        from django.contrib.gis.geos import LineString

        geom = LineString([(-6.0, 38.0), (-6.1, 38.1)], srid=4326)
        rv = RouteVariant.objects.create(name="Variante A", route_geometry=geom)
        for i in range(5):
            Edition.objects.create(
                date=date(2025, 1, i + 1),
                name=f"Ed {i}",
                start_time=time(16, 30),
                route_variant=rv,
            )

        with django_assert_num_queries(1):
            # force_authenticate no genera query de BD
            # 1 query: SELECT editions JOIN route_variant (un solo JOIN)
            resp = auth_client.get("/api/v1/editions/")
        assert resp.status_code == 200

    def test_user_stats_fixed_queries(self, auth_client, user, edition, participation, django_assert_num_queries):
        """GET /stats/user/<pk>/ no debe generar queries extra por cada participación."""
        from apps.participations.models import Activity

        Activity.objects.create(participation=participation, elapsed_time_seconds=3600, is_valid=True)

        with django_assert_num_queries(2):
            # force_authenticate no genera query de BD
            # 1: user lookup (get_object_or_404)
            # 1: participations con select_related (edition + activity + classification)
            resp = auth_client.get(f"/api/v1/stats/user/{user.pk}/")
        assert resp.status_code == 200
        assert resp.data["total_participations"] == 1
        assert resp.data["total_valid"] == 1
