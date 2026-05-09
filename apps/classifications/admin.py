from django.contrib import admin
from .models import Classification


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = ["participation", "category", "time_formatted", "position_overall", "position_category"]
    list_filter = ["category", "participation__edition"]
