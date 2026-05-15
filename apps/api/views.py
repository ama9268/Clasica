import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from apps.accounts.models import UserProfile
from apps.editions.models import Edition
from apps.participations.models import Participation, Activity
from apps.classifications.models import Classification
from apps.classifications.utils import recalculate_positions
from .serializers import (
    UserSerializer, UserProfileSerializer, EditionSerializer,
    EditionDetailSerializer, ClassificationSerializer, UserStatsSerializer,
    EditionWriteSerializer, EditionMediaSerializer, RouteVariantSerializer,
)

logger = logging.getLogger(__name__)


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditionListAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        editions = Edition.objects.all().order_by("-date")
        return Response(EditionSerializer(editions, many=True).data)

    def post(self, request):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = EditionWriteSerializer(data=request.data)
        if serializer.is_valid():
            edition = serializer.save()
            if edition.route_gpx:
                from apps.editions.utils import parse_gpx_to_geometry_and_elevation
                geom, distance, ele_profile = parse_gpx_to_geometry_and_elevation(edition.route_gpx)
                if geom:
                    edition.route_geometry = geom
                    edition.route_distance_km = distance
                    edition.elevation_profile = ele_profile
                    edition.save(update_fields=["route_geometry", "route_distance_km", "elevation_profile"])
            return Response(EditionDetailSerializer(edition).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditionDetailAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        edition = get_object_or_404(Edition, pk=pk)
        return Response(EditionDetailSerializer(edition, context={"request": request}).data)

    def patch(self, request, pk):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        edition = get_object_or_404(Edition, pk=pk)
        serializer = EditionWriteSerializer(edition, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            if "route_gpx" in request.FILES:
                from apps.editions.utils import parse_gpx_to_geometry_and_elevation
                geom, distance, ele_profile = parse_gpx_to_geometry_and_elevation(edition.route_gpx)
                if geom:
                    edition.route_geometry = geom
                    edition.route_distance_km = distance
                    edition.elevation_profile = ele_profile
                    edition.save(update_fields=["route_geometry", "route_distance_km", "elevation_profile"])
            return Response(EditionDetailSerializer(edition).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        edition = get_object_or_404(Edition, pk=pk)
        if edition.has_started:
            return Response({"detail": "No se puede eliminar una edición que ya ha comenzado."}, status=status.HTTP_400_BAD_REQUEST)
        edition.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EditionRegisterAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        edition = get_object_or_404(Edition, pk=pk)
        if not edition.is_registration_open:
            return Response({"detail": "Inscripciones cerradas."}, status=status.HTTP_400_BAD_REQUEST)
        _, created = Participation.objects.get_or_create(user=request.user, edition=edition)
        return Response({"registered": True, "created": created})


class ActivityUploadAPIView(APIView):
    """
    La app móvil envía el track GPS al finalizar la prueba.
    POST { track_geojson: LineString GeoJSON, elapsed_time_seconds: int }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.contrib.gis.geos import LineString, GEOSException
        from apps.participations.tasks import validate_track

        edition = get_object_or_404(Edition, pk=pk)

        try:
            participation = Participation.objects.get(user=request.user, edition=edition)
        except Participation.DoesNotExist:
            return Response(
                {"detail": "No estás inscrito en esta edición."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        elapsed = request.data.get("elapsed_time_seconds")
        track_geojson = request.data.get("track_geojson")
        avg_speed = request.data.get("average_moving_speed")

        if not elapsed or not track_geojson:
            return Response(
                {"detail": "elapsed_time_seconds y track_geojson son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            coords = track_geojson["coordinates"]
            track_geometry = LineString(coords, srid=4326)
        except (KeyError, TypeError, GEOSException):
            return Response({"detail": "track_geojson inválido."}, status=status.HTTP_400_BAD_REQUEST)

        score, is_valid = 0.0, False
        if edition.route_geometry:
            score, is_valid = validate_track(edition.route_geometry, track_geometry)
        # track_geometry se usa solo para validación; no se persiste

        activity, _ = Activity.objects.update_or_create(
            participation=participation,
            defaults={
                "elapsed_time_seconds": int(elapsed),
                "is_valid": is_valid,
                "validation_score": score,
                "average_moving_speed": float(avg_speed) if avg_speed is not None else None,
            },
        )

        if is_valid:
            recalculate_positions(edition)
            if edition.status == Edition.STATUS_OPEN:
                edition.status = Edition.STATUS_PUBLISHED
                edition.save(update_fields=["status"])

        return Response({
            "is_valid": is_valid,
            "validation_score": round(score, 3),
            "elapsed_time_seconds": activity.elapsed_time_seconds,
            "elapsed_formatted": activity.elapsed_formatted,
            "average_moving_speed": activity.average_moving_speed,
        })


class GeneralClassificationAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        from django.db.models import Count, Q
        stats = (
            Participation.objects.values(
                "user__pk", "user__full_name", "user__username", "user__club"
            )
            .annotate(
                total=Count("id"),
                valid=Count("activity", filter=Q(activity__is_valid=True)),
            )
            .order_by("-valid", "-total")
        )
        return Response(list(stats))


class UserStatsAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        user = get_object_or_404(UserProfile, pk=pk)
        participations = (
            Participation.objects.filter(user=user)
            .select_related("edition", "activity", "classification")
            .order_by("-edition__date")
        )
        return Response(UserStatsSerializer(user, context={"participations": participations}).data)


class EditionMediaListCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        edition = get_object_or_404(Edition, pk=pk)
        media = edition.media.all()
        return Response(EditionMediaSerializer(media, many=True).data)

    def post(self, request, pk):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        edition = get_object_or_404(Edition, pk=pk)
        data = request.data.copy()
        data['edition'] = edition.pk
        serializer = EditionMediaSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditionMediaDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        from apps.editions.models import EditionMedia
        media = get_object_or_404(EditionMedia, pk=pk)
        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteVariantListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.editions.models import RouteVariant
        variants = RouteVariant.objects.all()
        return Response(RouteVariantSerializer(variants, many=True).data)


# ── Strava ────────────────────────────────────────────────────────────────────

class StravaAuthUrlAPIView(APIView):
    """
    GET /auth/strava/auth-url/?redirect_uri=<uri>
    Genera un state CSRF, lo guarda en caché vinculado al user, y devuelve
    {"auth_url": "...", "state": "<token>"}.
    El cliente debe reenviar el state en el POST /auth/strava/connect/.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import secrets
        from django.conf import settings as conf
        from django.core.cache import cache
        from apps.accounts.services.strava import StravaClient

        # 'web' como redirect_uri indica que se usa el callback web del servidor.
        # Strava solo acepta http/https, por lo que la app móvil delega en el flujo web.
        redirect_uri_param = request.query_params.get("redirect_uri", "")
        if not redirect_uri_param:
            return Response({"detail": "redirect_uri es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        redirect_uri = (
            conf.STRAVA_REDIRECT_URI
            if redirect_uri_param == "web"
            else redirect_uri_param
        )

        state = secrets.token_urlsafe(24)
        cache.set(f"strava_oauth_state_{request.user.pk}", state, timeout=600)
        auth_url = StravaClient.get_auth_url(redirect_uri=redirect_uri, state=state)
        return Response({"auth_url": auth_url, "state": state})


class StravaConnectAPIView(APIView):
    """POST /auth/strava/connect/ {code, redirect_uri, state} → guarda tokens en UserProfile."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.cache import cache
        from apps.accounts.services.strava import StravaClient, StravaError
        code = request.data.get("code")
        redirect_uri = request.data.get("redirect_uri")
        returned_state = request.data.get("state", "")

        if not code or not redirect_uri:
            return Response({"detail": "code y redirect_uri son obligatorios."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar CSRF: el state devuelto debe coincidir con el generado para este usuario
        cache_key = f"strava_oauth_state_{request.user.pk}"
        expected_state = cache.get(cache_key)
        if not expected_state or returned_state != expected_state:
            logger.warning("Strava OAuth state mismatch para user=%s", request.user.pk)
            return Response({"detail": "Estado OAuth inválido. Inicia el proceso de nuevo."}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(cache_key)

        try:
            payload = StravaClient.exchange_code(code=code, redirect_uri=redirect_uri)
        except StravaError as exc:
            logger.warning("Strava connect error: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        athlete = payload.get("athlete", {})
        import datetime
        from django.utils import timezone as tz
        user = request.user
        user.strava_athlete_id = athlete.get("id") or payload.get("athlete_id")
        user.strava_access_token = payload.get("access_token", "")
        user.strava_refresh_token = payload.get("refresh_token", "")
        expires_at = payload.get("expires_at")
        if expires_at:
            user.strava_token_expires_at = tz.make_aware(
                datetime.datetime.fromtimestamp(expires_at),
                tz.get_current_timezone(),
            )
        user.save(update_fields=[
            "strava_athlete_id", "strava_access_token",
            "strava_refresh_token", "strava_token_expires_at",
        ])
        return Response({"strava_athlete_id": user.strava_athlete_id})


class StravaDisconnectAPIView(APIView):
    """POST /auth/strava/disconnect/ → revoca token y limpia campos."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.accounts.services.strava import StravaClient
        if not request.user.strava_connected:
            return Response({"detail": "No hay cuenta Strava conectada."}, status=status.HTTP_400_BAD_REQUEST)
        StravaClient(request.user).revoke_token()
        return Response({"disconnected": True})


class StravaActivitiesAPIView(APIView):
    """GET /editions/<pk>/strava-activities/ → lista actividades Strava del usuario en la fecha de la edición."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.accounts.services.strava import StravaClient, StravaError
        edition = get_object_or_404(Edition, pk=pk)
        if not request.user.strava_connected:
            return Response({"detail": "No tienes Strava conectado."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            activities = StravaClient(request.user).get_activities_on_date(edition.date)
        except StravaError as exc:
            logger.warning("Strava activities error user=%s: %s", request.user.pk, exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(activities)


class StravaActivityUploadAPIView(APIView):
    """POST /editions/<pk>/activity/strava/ {strava_activity_id} → descarga, valida y guarda."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone as tz
        import datetime
        from apps.accounts.services.strava import StravaClient, StravaError
        from apps.participations.tasks import validate_track

        edition = get_object_or_404(Edition, pk=pk)

        # Verificar inscripción
        try:
            participation = Participation.objects.get(user=request.user, edition=edition)
        except Participation.DoesNotExist:
            return Response({"detail": "No estás inscrito en esta edición."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar Strava conectado
        if not request.user.strava_connected:
            return Response({"detail": "No tienes Strava conectado."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar ventana de tiempo
        from django.conf import settings as conf
        window_hours = getattr(conf, "STRAVA_ACTIVITY_UPLOAD_WINDOW_HOURS", 24)
        deadline = tz.make_aware(
            datetime.datetime.combine(edition.date, datetime.time.max),
            tz.get_current_timezone(),
        ) + datetime.timedelta(hours=window_hours)
        if tz.now() > deadline:
            return Response(
                {"detail": f"El plazo para subir desde Strava ({window_hours}h tras la edición) ha expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        strava_activity_id = request.data.get("strava_activity_id")
        if not strava_activity_id:
            return Response({"detail": "strava_activity_id es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        # Descargar stream y convertir a LineString
        try:
            track_geometry = StravaClient(request.user).get_activity_linestring(int(strava_activity_id))
        except StravaError as exc:
            logger.warning("Strava stream error user=%s activity=%s: %s", request.user.pk, strava_activity_id, exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        # Validar con PostGIS (igual que el flujo GPS móvil)
        score, is_valid = 0.0, False
        route_geom = edition.route_geom
        if route_geom:
            score, is_valid = validate_track(route_geom, track_geometry)

        activity, _ = Activity.objects.update_or_create(
            participation=participation,
            defaults={
                "is_valid": is_valid,
                "validation_score": score,
                "source": Activity.SOURCE_STRAVA,
                "strava_activity_id": int(strava_activity_id),
                # elapsed_time y speed no se obtienen del stream; se ponen a None si no estaban
            },
        )

        if is_valid:
            recalculate_positions(edition)
            if edition.status == Edition.STATUS_OPEN:
                edition.status = Edition.STATUS_PUBLISHED
                edition.save(update_fields=["status"])

        return Response({
            "is_valid": is_valid,
            "validation_score": round(score, 3),
            "source": Activity.SOURCE_STRAVA,
            "elapsed_time_seconds": activity.elapsed_time_seconds,
            "elapsed_formatted": activity.elapsed_formatted,
            "average_moving_speed": activity.average_moving_speed,
        })


class StravaWebhookAPIView(APIView):
    """
    GET  /strava/webhook/ → verificación de suscripción (hub.challenge)
    POST /strava/webhook/ → recepción de eventos push (fase 2)
    """
    permission_classes = []  # Strava no envía credenciales de usuario

    def get(self, request):
        hub_mode = request.query_params.get("hub.mode")
        hub_challenge = request.query_params.get("hub.challenge")
        hub_verify_token = request.query_params.get("hub.verify_token")

        from django.conf import settings as conf
        expected_token = getattr(conf, "STRAVA_WEBHOOK_VERIFY_TOKEN", "clasica_verify")
        if hub_mode == "subscribe" and hub_verify_token == expected_token:
            return Response({"hub.challenge": hub_challenge})
        return Response(status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        # Fase 2: procesar eventos push de Strava
        logger.info("Strava webhook event: %s", request.data)
        return Response({"status": "ok"})
