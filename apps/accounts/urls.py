from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("strava/connect/", views.strava_connect, name="strava_connect"),
    path("strava/callback/", views.strava_callback, name="strava_callback"),
    path("strava/disconnect/", views.strava_disconnect, name="strava_disconnect"),
]
