from django.contrib import admin
from .models import Edition, EditionMedia


class EditionMediaInline(admin.TabularInline):
    model = EditionMedia
    extra = 1
    fields = ["media_type", "photo", "video_url", "caption", "order"]


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "status", "route_distance_km"]
    list_filter = ["status"]
    ordering = ["-date"]
    inlines = [EditionMediaInline]


@admin.register(EditionMedia)
class EditionMediaAdmin(admin.ModelAdmin):
    list_display = ["edition", "media_type", "caption", "order"]
    list_filter = ["media_type", "edition"]
