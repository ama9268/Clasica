from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    list_display = ["username", "full_name", "club", "birth_date"]
    list_filter = ["is_staff", "club"]
    fieldsets = UserAdmin.fieldsets + (
        ("Perfil ciclista", {"fields": ("full_name", "birth_date", "club", "photo")}),
    )
    readonly_fields = []
