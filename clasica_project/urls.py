from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from apps.api.views import HealthCheckAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("editions/", include("apps.editions.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("api/health/", HealthCheckAPIView.as_view(), name="health-check"),
    path("", include("apps.editions.public_urls")),
    # Sirve /media/ tanto en desarrollo como en producción.
    # django.conf.urls.static.static() solo funciona con DEBUG=True.
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
