from django.contrib import admin
from .models import Participation, Activity


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ["user", "edition", "registered_at"]
    list_filter = ["edition"]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["participation", "elapsed_formatted", "is_valid", "validation_score"]
    list_filter = ["is_valid"]
    readonly_fields = ["recorded_at"]
