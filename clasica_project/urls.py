from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("editions/", include("apps.editions.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("", include("apps.editions.public_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
