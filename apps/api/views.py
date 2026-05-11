import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
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


class EditionDetailAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        edition = get_object_or_404(Edition, pk=pk)
        return Response(EditionDetailSerializer(edition, context={"request": request}).data)


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

        activity, _ = Activity.objects.update_or_create(
            participation=participation,
            defaults={
                "elapsed_time_seconds": int(elapsed),
                "track_geometry": track_geometry,
                "is_valid": is_valid,
                "validation_score": score,
                "average_moving_speed": float(avg_speed) if avg_speed is not None else None,
            },
        )

        if is_valid:
            recalculate_positions(edition)

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
