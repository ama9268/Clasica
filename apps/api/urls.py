from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path("auth/register/", views.RegisterAPIView.as_view(), name="api_register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="api_login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),
    path("auth/me/", views.MeAPIView.as_view(), name="api_me"),
    path("editions/", views.EditionListAPIView.as_view(), name="api_editions"),
    path("editions/<int:pk>/", views.EditionDetailAPIView.as_view(), name="api_edition_detail"),
    path("editions/<int:pk>/register/", views.EditionRegisterAPIView.as_view(), name="api_edition_register"),
    path("editions/<int:pk>/activity/", views.ActivityUploadAPIView.as_view(), name="api_activity_upload"),
    path("editions/<int:pk>/media/", views.EditionMediaListCreateAPIView.as_view(), name="edition-media-list"),
    path("media/<int:pk>/", views.EditionMediaDeleteAPIView.as_view(), name="media-detail"),
    path("route-variants/", views.RouteVariantListAPIView.as_view(), name="route-variant-list"),
    path("classifications/general/", views.GeneralClassificationAPIView.as_view(), name="api_general"),
    path("stats/user/<int:pk>/", views.UserStatsAPIView.as_view(), name="api_user_stats"),
]
