import pytest
from datetime import date, time

from django.contrib.gis.geos import LineString
from django.core.cache import cache

from apps.accounts.models import UserProfile
from apps.editions.models import Edition
from apps.participations.models import Participation


@pytest.fixture(autouse=True)
def use_locmem_cache(settings):
    """Sustituye el caché Redis por LocMemCache en todos los tests.
    Evita que los tests dependan de un servidor Redis local y aísla
    los contadores de throttling entre pruebas."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    cache.clear()


@pytest.fixture
def user(db):
    return UserProfile.objects.create_user(
        username="ciclista1",
        password="testpass123",
        email="ciclista1@test.com",
        full_name="Ciclista Test",
        birth_date=date(1985, 1, 1),  # 41 años en 2026 → M40
    )


@pytest.fixture
def user2(db):
    return UserProfile.objects.create_user(
        username="ciclista2",
        password="testpass123",
        email="ciclista2@test.com",
        full_name="Ciclista Dos",
        birth_date=date(1973, 1, 1),  # 53 años en 2026 → M50
    )


@pytest.fixture
def route_geom():
    # Ruta lineal en Llerena (zona del proyecto), suficiente para ST_DumpPoints
    return LineString(
        [(-6.00, 38.00), (-6.02, 38.02), (-6.04, 38.04), (-6.06, 38.06)],
        srid=4326,
    )


@pytest.fixture
def edition(db, route_geom):
    return Edition.objects.create(
        date=date(2026, 6, 1),
        name="Edición Test",
        start_time=time(16, 30),
        route_geometry=route_geom,
        status=Edition.STATUS_OPEN,
    )


@pytest.fixture
def participation(db, user, edition):
    return Participation.objects.create(user=user, edition=edition)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client
