from django.contrib import admin
from .models import Participation, StravaActivity


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ["user", "edition", "registered_at"]
    list_filter = ["edition"]


@admin.register(StravaActivity)
class StravaActivityAdmin(admin.ModelAdmin):
    list_display = ["participation", "elapsed_formatted", "is_valid", "validation_score"]
    list_filter = ["is_valid"]
    readonly_fields = ["strava_activity_id", "imported_at"]
