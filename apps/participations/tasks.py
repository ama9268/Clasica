import logging
from math import radians, cos, sin, asin, sqrt
from celery import shared_task
from django.conf import settings
import requests

logger = logging.getLogger(__name__)

STRAVA_API = "https://www.strava.com/api/v3"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_strava_activity(self, activity_id: int, athlete_id: int):
    from apps.accounts.models import UserProfile
    from apps.editions.models import Edition
    from apps.participations.models import Participation, StravaActivity
    from apps.classifications.models import Classification, get_category
    from django.utils import timezone
    import datetime

    try:
        user = UserProfile.objects.get(strava_athlete_id=athlete_id)
    except UserProfile.DoesNotExist:
        logger.warning("Webhook: atleta Strava %s no registrado", athlete_id)
        return

    token = _get_valid_token(user)
    if not token:
        logger.error("No se pudo obtener token para usuario %s", user.pk)
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Obtener detalles de la actividad
    detail = requests.get(f"{STRAVA_API}/activities/{activity_id}", headers=headers, timeout=10)
    if detail.status_code != 200:
        logger.error("Error obteniendo actividad %s: %s", activity_id, detail.status_code)
        raise self.retry()

    detail_data = detail.json()
    activity_type = detail_data.get("sport_type", "").lower()
    if "ride" not in activity_type and "cycling" not in activity_type:
        logger.info("Actividad %s ignorada (tipo: %s)", activity_id, activity_type)
        return

    activity_date = detail_data.get("start_date_local", "")[:10]
    try:
        edition = Edition.objects.get(date=activity_date, status__in=[
            Edition.STATUS_OPEN, Edition.STATUS_CLOSED
        ])
    except Edition.DoesNotExist:
        logger.info("No hay edición activa para fecha %s", activity_date)
        return

    participation, _ = Participation.objects.get_or_create(user=user, edition=edition)

    # Obtener GPS streams
    streams_r = requests.get(
        f"{STRAVA_API}/activities/{activity_id}/streams",
        params={"keys": "latlng,time", "series_type": "time"},
        headers=headers,
        timeout=10,
    )
    if streams_r.status_code != 200:
        logger.error("Error obteniendo streams %s: %s", activity_id, streams_r.status_code)
        raise self.retry()

    coords = []
    for stream in streams_r.json():
        if stream["type"] == "latlng":
            coords = [[pt[1], pt[0]] for pt in stream["data"]]  # [lon, lat]
            break

    track_geojson = {"type": "LineString", "coordinates": coords} if coords else None
    elapsed = detail_data.get("elapsed_time", 0)

    score, is_valid = 0.0, False
    if coords and edition.route_geojson:
        score, is_valid = validate_track(edition.route_geojson["coordinates"], coords)

    StravaActivity.objects.update_or_create(
        participation=participation,
        defaults={
            "strava_activity_id": activity_id,
            "elapsed_time_seconds": elapsed,
            "track_geojson": track_geojson,
            "is_valid": is_valid,
            "validation_score": score,
        },
    )
    logger.info("Actividad %s importada (válida=%s, score=%.2f)", activity_id, is_valid, score)


def _get_valid_token(user) -> str | None:
    from django.utils import timezone
    import datetime
    if user.strava_token_expired:
        refreshed = _refresh_token(user)
        if not refreshed:
            return None
    return user.strava_access_token


def _refresh_token(user) -> bool:
    from django.conf import settings
    from django.utils import timezone
    import datetime
    r = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": settings.STRAVA_CLIENT_ID,
        "client_secret": settings.STRAVA_CLIENT_SECRET,
        "refresh_token": user.strava_refresh_token,
        "grant_type": "refresh_token",
    }, timeout=10)
    if r.status_code != 200:
        return False
    data = r.json()
    user.strava_access_token = data["access_token"]
    user.strava_refresh_token = data["refresh_token"]
    user.strava_token_expires_at = timezone.datetime.fromtimestamp(
        data["expires_at"], tz=timezone.utc
    )
    user.save(update_fields=["strava_access_token", "strava_refresh_token", "strava_token_expires_at"])
    return True


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * asin(sqrt(a))


def validate_track(
    official_coords: list,
    user_coords: list,
    threshold_m: float | None = None,
    min_score: float | None = None,
) -> tuple[float, bool]:
    from django.conf import settings
    threshold_m = threshold_m or settings.GPX_MATCH_THRESHOLD_METERS
    min_score = min_score or settings.GPX_MATCH_MIN_SCORE

    if not official_coords or not user_coords:
        return 0.0, False

    matched = 0
    for off_lon, off_lat in official_coords:
        closest = min(
            _haversine(off_lat, off_lon, u_lat, u_lon)
            for u_lon, u_lat in user_coords
        )
        if closest <= threshold_m:
            matched += 1

    score = matched / len(official_coords)
    return round(score, 4), score >= min_score
