from rest_framework import serializers
from apps.accounts.models import UserProfile
from apps.editions.models import Edition
from apps.classifications.models import Classification


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
    strava_connected = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ["id", "username", "email", "full_name", "birth_date", "club",
                  "photo", "strava_connected"]
        read_only_fields = ["id", "username", "strava_connected"]

    def get_strava_connected(self, obj) -> bool:
        return obj.strava_connected


class EditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edition
        fields = ["id", "date", "name", "route_distance_km", "status",
                  "is_registration_open", "results_published"]


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
    route_geojson = serializers.JSONField()
    user_registered = serializers.SerializerMethodField()

    class Meta(EditionSerializer.Meta):
        fields = EditionSerializer.Meta.fields + ["route_geojson", "classifications", "user_registered"]

    def get_classifications(self, obj):
        qs = Classification.objects.filter(
            participation__edition=obj,
            participation__strava_activity__is_valid=True,
        ).select_related("participation__user").order_by("position_overall")
        return ClassificationSerializer(qs, many=True).data

    def get_user_registered(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.participations.filter(user=request.user).exists()


class UserStatsSerializer(serializers.ModelSerializer):
    total_participations = serializers.SerializerMethodField()
    total_valid = serializers.SerializerMethodField()
    participations = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ["id", "full_name", "username", "club", "photo",
                  "total_participations", "total_valid", "participations"]

    def get_total_participations(self, obj) -> int:
        return self.context["participations"].count()

    def get_total_valid(self, obj) -> int:
        return self.context["participations"].filter(
            strava_activity__is_valid=True
        ).count()

    def get_participations(self, obj):
        result = []
        for p in self.context["participations"]:
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
                sa = p.strava_activity
                entry["is_valid"] = sa.is_valid
                if sa.is_valid:
                    entry["time_formatted"] = sa.elapsed_formatted
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
