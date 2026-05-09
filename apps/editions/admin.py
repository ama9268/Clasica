from django.contrib import admin
from .models import Edition, EditionMedia, RouteVariant


class EditionMediaInline(admin.TabularInline):
    model = EditionMedia
    extra = 1
    fields = ["media_type", "photo", "video_url", "caption", "order"]


@admin.register(RouteVariant)
class RouteVariantAdmin(admin.ModelAdmin):
    list_display = ["name", "route_distance_km", "created_at"]
    search_fields = ["name"]
    # Excluimos los campos automáticos para que no estorben
    exclude = ["route_geometry", "elevation_profile", "route_distance_km"]


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "status", "get_distance"]
    list_filter = ["status"]
    ordering = ["-date"]
    inlines = [EditionMediaInline]
    
    fieldsets = [
        ("Información General", {
            "fields": ["name", "date", "start_time", "status"]
        }),
        ("Ruta y Recorrido", {
            "description": "IMPORTANTE: Elige una variante (Larga/Corta/Mini) O sube un GPX propio.",
            "fields": ["route_variant", "route_gpx"]
        }),
        ("Datos Técnicos (Auto-generados)", {
            "classes": ["collapse"],
            "fields": ["route_geometry", "route_distance_km", "elevation_profile"]
        }),
    ]

    def get_distance(self, obj):
        return f"{obj.get_route_distance} km" if obj.get_route_distance else "-"
    get_distance.short_description = "Distancia"


@admin.register(EditionMedia)
class EditionMediaAdmin(admin.ModelAdmin):
    list_display = ["edition", "media_type", "caption", "order"]
    list_filter = ["media_type", "edition"]
