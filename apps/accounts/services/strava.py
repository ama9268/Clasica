import datetime
import logging
import urllib.parse

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
DEAUTHORIZE_URL = "https://www.strava.com/oauth/deauthorize"
API_BASE = "https://www.strava.com/api/v3"


class StravaError(Exception):
    pass


class StravaClient:
    def __init__(self, user):
        self.user = user

    # ── OAuth estático ────────────────────────────────────────────────────────

    @staticmethod
    def get_auth_url(redirect_uri: str, state: str = "") -> str:
        params = {
            "client_id": settings.STRAVA_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "activity:read",
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def exchange_code(code: str, redirect_uri: str) -> dict:
        resp = requests.post(TOKEN_URL, data={
            "client_id": settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }, timeout=10)
        if not resp.ok:
            raise StravaError(f"Token exchange failed: {resp.text}")
        return resp.json()

    # ── Gestión de tokens ─────────────────────────────────────────────────────

    def _ensure_fresh_token(self) -> str:
        user = self.user
        if not user.strava_refresh_token:
            raise StravaError("No hay refresh token almacenado.")

        if user.strava_token_expires_at and user.strava_token_expires_at > timezone.now():
            return user.strava_access_token

        resp = requests.post(TOKEN_URL, data={
            "client_id": settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": user.strava_refresh_token,
        }, timeout=10)
        if not resp.ok:
            raise StravaError(f"Token refresh failed: {resp.text}")

        data = resp.json()
        user.strava_access_token = data["access_token"]
        user.strava_refresh_token = data["refresh_token"]
        user.strava_token_expires_at = timezone.make_aware(
            datetime.datetime.fromtimestamp(data["expires_at"]),
            timezone.get_current_timezone(),
        )
        user.save(update_fields=["strava_access_token", "strava_refresh_token", "strava_token_expires_at"])
        return user.strava_access_token

    def _get(self, path: str, **params) -> dict | list:
        token = self._ensure_fresh_token()
        resp = requests.get(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        if not resp.ok:
            raise StravaError(f"Strava API error {resp.status_code}: {resp.text}")
        return resp.json()

    # ── Actividades ───────────────────────────────────────────────────────────

    def get_activities_on_date(self, date: datetime.date) -> list[dict]:
        """Devuelve actividades Ride del atleta en la fecha dada (hora local Madrid)."""
        tz = timezone.get_current_timezone()
        start = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=tz)
        end = datetime.datetime.combine(date, datetime.time.max).replace(tzinfo=tz)

        activities = self._get(
            "/athlete/activities",
            after=int(start.timestamp()),
            before=int(end.timestamp()),
            per_page=30,
        )

        return [
            {
                "id": a["id"],
                "name": a.get("name", ""),
                "type": a.get("type", ""),
                "start_date_local": a.get("start_date_local", ""),
                "distance": round(a.get("distance", 0) / 1000, 2),  # km
                "elapsed_time": a.get("elapsed_time", 0),
                "moving_time": a.get("moving_time", 0),
            }
            for a in activities
            if a.get("type") in ("Ride", "VirtualRide", "GravelRide", "EBikeRide")
        ]

    def get_activity_linestring(self, activity_id: int):
        """Descarga el stream latlng y lo convierte a GEOSLineString(srid=4326)."""
        from django.contrib.gis.geos import LineString as GEOSLineString, GEOSException

        data = self._get(f"/activities/{activity_id}/streams", keys="latlng", key_by_type=True)

        try:
            latlng = data["latlng"]["data"]
        except (KeyError, TypeError):
            raise StravaError("La actividad no tiene stream de coordenadas GPS.")

        if len(latlng) < 2:
            raise StravaError("Track demasiado corto para validar.")

        # Strava devuelve [lat, lon]; GEOSLineString espera (lon, lat)
        coords = [(pt[1], pt[0]) for pt in latlng]
        try:
            return GEOSLineString(coords, srid=4326)
        except GEOSException as exc:
            raise StravaError(f"No se pudo construir la geometría: {exc}")

    # ── Desconexión ───────────────────────────────────────────────────────────

    def revoke_token(self) -> None:
        try:
            token = self._ensure_fresh_token()
            requests.post(DEAUTHORIZE_URL, data={"access_token": token}, timeout=10)
        except Exception:
            pass  # Si falla la revocación, limpiamos igualmente
        finally:
            self.user.strava_athlete_id = None
            self.user.strava_access_token = ""
            self.user.strava_refresh_token = ""
            self.user.strava_token_expires_at = None
            self.user.save(update_fields=[
                "strava_athlete_id", "strava_access_token",
                "strava_refresh_token", "strava_token_expires_at",
            ])
