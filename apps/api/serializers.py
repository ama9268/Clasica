from rest_framework import serializers
from rest_framework_gis.fields import GeometryField
from apps.accounts.models import UserProfile
from apps.editions.models import Edition, EditionMedia, RouteVariant
from apps.classifications.models import Classification
from apps.editions.services.aemet import get_weather_forecast_for_edition


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = UserProfile
        fields = ["username", "email", "password", "full_name", "birth_date", "club"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = UserProfile(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    strava_connected = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id", "username", "email", "full_name", "birth_date", "club", "photo", "is_staff",
            "strava_connected", "strava_athlete_id",
        ]
        read_only_fields = ["id", "username", "is_staff", "strava_connected", "strava_athlete_id"]


class RouteVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteVariant
        fields = ["id", "name", "description", "route_distance_km"]


class EditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edition
        fields = ["id", "date", "name", "start_time", "route_distance_km", "status",
                  "is_registration_open", "results_published"]


class EditionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edition
        fields = ["date", "name", "start_time", "route_variant", "route_gpx", "status"]


class EditionMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EditionMedia
        fields = ["id", "edition", "media_type", "photo", "video_url", "caption", "order", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class ClassificationSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="participation.user.pk")
    full_name = serializers.CharField(source="participation.user.full_name")
    club = serializers.CharField(source="participation.user.club")
    time_formatted = serializers.CharField()

    class Meta:
        model = Classification
        fields = ["position_overall", "position_category", "category",
                  "time_seconds", "time_formatted", "user_id", "full_name", "club"]


class EditionDetailSerializer(EditionSerializer):
    classifications = serializers.SerializerMethodField()
    route_geojson = GeometryField(source="route_geom", read_only=True)
    is_live = serializers.SerializerMethodField()
    elevation_profile = serializers.SerializerMethodField()
    user_registered = serializers.SerializerMethodField()
    weather = serializers.SerializerMethodField()
    media = EditionMediaSerializer(many=True, read_only=True)
    participants_count = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()

    class Meta(EditionSerializer.Meta):
        fields = EditionSerializer.Meta.fields + [
            "route_geojson", "is_live", "elevation_profile",
            "classifications", "user_registered", "weather", "media",
            "participants_count", "participants",
        ]

    def get_classifications(self, obj):
        qs = (
            Classification.objects.filter(
                participation__edition=obj,
                participation__activity__is_valid=True,
            )
            .select_related("participation__user")
            .order_by("position_overall")
        )
        return ClassificationSerializer(qs, many=True).data

    def get_is_live(self, obj) -> bool:
        return obj.is_live

    def get_elevation_profile(self, obj):
        return obj.get_elevation_profile

    def get_user_registered(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.participations.filter(user=request.user).exists()

    def get_weather(self, obj):
        if obj.status != Edition.STATUS_OPEN:
            return None
        return get_weather_forecast_for_edition(obj.date, start_hour=obj.start_time.hour)

    def get_participants_count(self, obj) -> int:
        return obj.participations.count()

    def get_participants(self, obj):
        if obj.status != Edition.STATUS_OPEN:
            return []
        return list(
            obj.participations.select_related("user")
            .values("user__full_name", "user__club")
            .order_by("registered_at")
        )


class UserStatsSerializer(serializers.ModelSerializer):
    total_participations = serializers.SerializerMethodField()
    total_valid = serializers.SerializerMethodField()
    participations = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ["id", "full_name", "username", "club", "photo",
                  "total_participations", "total_valid", "participations"]

    def _participations_list(self):
        """Evalúa el queryset una sola vez y lo cachea en context."""
        if "_participations_list" not in self.context:
            self.context["_participations_list"] = list(self.context["participations"])
        return self.context["_participations_list"]

    def get_total_participations(self, obj) -> int:
        return len(self._participations_list())

    def get_total_valid(self, obj) -> int:
        # RelatedObjectDoesNotExist hereda de AttributeError → hasattr lo captura
        return sum(
            1 for p in self._participations_list()
            if hasattr(p, "activity") and p.activity.is_valid
        )

    def get_participations(self, obj):
        result = []
        for p in self._participations_list():
            entry = {
                "edition_id": p.edition.pk,
                "edition_name": p.edition.name,
                "edition_date": str(p.edition.date),
                "is_valid": False,
                "time_formatted": "—",
                "position_overall": None,
                "category": None,
            }
            try:
                a = p.activity
                entry["is_valid"] = a.is_valid
                if a.is_valid:
                    entry["time_formatted"] = a.elapsed_formatted
            except Exception:
                pass
            try:
                cl = p.classification
                entry["position_overall"] = cl.position_overall
                entry["category"] = cl.category
                entry["time_formatted"] = cl.time_formatted
            except Exception:
                pass
            result.append(entry)
        return result


class ActivityUploadSerializer(serializers.Serializer):
    # Un ciclista no puede terminar en menos de 1 s ni en más de 18 h (64800 s)
    elapsed_time_seconds = serializers.IntegerField(min_value=1, max_value=64800)
    # Velocidad media en km/h: mínimo razonable 0.1, máximo sprint ~120
    average_moving_speed = serializers.FloatField(
        min_value=0.1, max_value=120.0, required=False, allow_null=True
    )
    track_geojson = serializers.DictField()

    def validate_track_geojson(self, value):
        from django.contrib.gis.geos import LineString, GEOSException

        if value.get("type") != "LineString":
            raise serializers.ValidationError("Debe ser de tipo LineString.")

        coords = value.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            raise serializers.ValidationError("Se necesitan al menos 2 coordenadas.")

        for coord in coords:
            if not isinstance(coord, (list, tuple)) or len(coord) < 2:
                raise serializers.ValidationError("Cada coordenada debe ser [lon, lat].")
            lon, lat = coord[0], coord[1]
            if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
                raise serializers.ValidationError("Las coordenadas deben ser numéricas.")
            if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                raise serializers.ValidationError(
                    f"Coordenada fuera de rango: [{lon}, {lat}]."
                )

        try:
            LineString(coords, srid=4326)
        except GEOSException as exc:
            raise serializers.ValidationError(f"Geometría inválida: {exc}")

        return value
