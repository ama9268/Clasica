from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    list_display = ["username", "full_name", "club", "strava_connected", "birth_date"]
    list_filter = ["is_staff", "club"]
    fieldsets = UserAdmin.fieldsets + (
        ("Perfil ciclista", {"fields": ("full_name", "birth_date", "club", "photo")}),
        ("Strava", {"fields": ("strava_athlete_id",), "classes": ("collapse",)}),
    )
    readonly_fields = ["strava_athlete_id"]
