import logging
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.models import UserProfile
from apps.editions.models import Edition
from apps.participations.models import Participation
from apps.classifications.models import Classification
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
        editions = Edition.objects.all()
        return Response(EditionSerializer(editions, many=True).data)


class EditionDetailAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        try:
            edition = Edition.objects.get(pk=pk)
        except Edition.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(EditionDetailSerializer(edition, context={"request": request}).data)


class EditionRegisterAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            edition = Edition.objects.get(pk=pk)
        except Edition.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not edition.is_registration_open:
            return Response({"detail": "Inscripciones cerradas."}, status=status.HTTP_400_BAD_REQUEST)
        _, created = Participation.objects.get_or_create(user=request.user, edition=edition)
        return Response({"registered": True, "created": created}, status=status.HTTP_200_OK)


class GeneralClassificationAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        from django.db.models import Count, Q
        stats = (
            Participation.objects.values("user__pk", "user__full_name", "user__username", "user__club")
            .annotate(
                total=Count("id"),
                valid=Count("strava_activity", filter=Q(strava_activity__is_valid=True)),
            )
            .order_by("-valid", "-total")
        )
        return Response(list(stats))


class UserStatsAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        try:
            user = UserProfile.objects.get(pk=pk)
        except UserProfile.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        participations = (
            Participation.objects.filter(user=user)
            .select_related("edition", "strava_activity", "classification")
            .order_by("-edition__date")
        )
        return Response(UserStatsSerializer(user, context={"participations": participations}).data)


class StravaConnectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings
        from urllib.parse import urlencode
        params = {
            "client_id": settings.STRAVA_CLIENT_ID,
            "redirect_uri": settings.STRAVA_REDIRECT_URI,
            "response_type": "code",
            "scope": "activity:read_all",
        }
        url = "https://www.strava.com/oauth/authorize?" + urlencode(params)
        return Response({"authorization_url": url})


class StravaDisconnectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user.strava_athlete_id = None
        user.strava_access_token = ""
        user.strava_refresh_token = ""
        user.strava_token_expires_at = None
        user.save(update_fields=["strava_athlete_id", "strava_access_token",
                                  "strava_refresh_token", "strava_token_expires_at"])
        return Response({"disconnected": True})
