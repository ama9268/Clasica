import pytest
from datetime import date, time, datetime
from unittest.mock import patch

from freezegun import freeze_time

from apps.editions.models import Edition
from apps.editions.tasks import auto_close_expired_editions
from apps.participations.models import Activity, Participation


@pytest.mark.django_db
class TestAutoCloseExpiredEditions:
    """
    Llama a la tarea directamente (sin broker Celery) para testear su lógica.
    El tiempo se congela con freezegun en la zona Europe/Madrid (TIME_ZONE del proyecto).
    """

    def _make_today_edition(self, frozen_date):
        return Edition.objects.create(
            date=frozen_date,
            name="Edición de hoy",
            start_time=time(16, 30),
            status=Edition.STATUS_OPEN,
        )

    @freeze_time("2026-06-01 20:00:00")  # 20:00 UTC → 22:00 CEST (UTC+2) → después de 21:30
    def test_closes_edition_without_finishers(self, db):
        edition = self._make_today_edition(date(2026, 6, 1))
        auto_close_expired_editions()
        edition.refresh_from_db()
        assert edition.status == Edition.STATUS_CLOSED

    @freeze_time("2026-06-01 20:00:00")  # 22:00 CEST → después de 21:30
    def test_publishes_edition_with_finishers(self, user, db):
        edition = self._make_today_edition(date(2026, 6, 1))
        participation = Participation.objects.create(user=user, edition=edition)
        Activity.objects.create(
            participation=participation,
            elapsed_time_seconds=3600,
            is_valid=True,
        )
        auto_close_expired_editions()
        edition.refresh_from_db()
        assert edition.status == Edition.STATUS_PUBLISHED

    @freeze_time("2026-06-01 16:00:00")  # 16:00 UTC → 18:00 CEST → antes de 21:30
    def test_no_op_before_cutoff(self, db):
        edition = self._make_today_edition(date(2026, 6, 1))
        auto_close_expired_editions()
        edition.refresh_from_db()
        assert edition.status == Edition.STATUS_OPEN

    @freeze_time("2026-06-01 20:00:00")  # 22:00 CEST
    def test_ignores_editions_from_other_dates(self, db):
        yesterday_edition = Edition.objects.create(
            date=date(2026, 5, 31),
            name="Edición de ayer",
            start_time=time(16, 30),
            status=Edition.STATUS_OPEN,
        )
        auto_close_expired_editions()
        yesterday_edition.refresh_from_db()
        # No se toca porque su date no es hoy (2026-06-01)
        assert yesterday_edition.status == Edition.STATUS_OPEN


# ── AEMET stale cache ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAEMETStaleCache:
    """Comprueba que get_weather sirve stale cache cuando AEMET no responde."""

    DATE = date(2026, 6, 1)
    HOUR = 16

    def test_stale_cache_served_when_aemet_fails(self, settings):
        from django.core.cache import cache
        from apps.editions.services.aemet import get_weather_forecast_for_edition, STALE_TTL

        settings.AEMET_API_KEY = "test_key"
        stale_data = {"temperatura": 25, "viento_dir": "N", "viento_vel": 10,
                      "lluvia": 0, "estado_cielo": "Despejado"}
        stale_key = f"aemet_stale_{self.DATE.isoformat()}_{self.HOUR}"
        cache.set(stale_key, stale_data, timeout=STALE_TTL)

        with patch("apps.editions.services.aemet._fetch_horaria", return_value=None), \
             patch("apps.editions.services.aemet._fetch_diaria", return_value=None):
            result = get_weather_forecast_for_edition(self.DATE, start_hour=self.HOUR)

        assert result == stale_data

    def test_returns_none_when_aemet_fails_and_no_stale(self, settings):
        from django.core.cache import cache
        from apps.editions.services.aemet import get_weather_forecast_for_edition

        settings.AEMET_API_KEY = "test_key"
        cache.clear()

        with patch("apps.editions.services.aemet._fetch_horaria", return_value=None), \
             patch("apps.editions.services.aemet._fetch_diaria", return_value=None):
            result = get_weather_forecast_for_edition(self.DATE, start_hour=self.HOUR)

        assert result is None

