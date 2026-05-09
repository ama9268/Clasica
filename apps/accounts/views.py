import logging
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import View, FormView, UpdateView
from django.contrib import messages
from django.conf import settings
from django.http import HttpRequest, HttpResponse
import requests

from .models import UserProfile
from .forms import RegisterForm, ProfileForm

logger = logging.getLogger(__name__)


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Bienvenido/a a La Clásica.")
        return super().form_valid(form)


class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        from django.shortcuts import render
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get("next", "/")
            return redirect(next_url)
        from django.shortcuts import render
        return render(request, self.template_name, {"error": "Credenciales incorrectas"})


class LogoutView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        return redirect("home")


class ProfileView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self):
        return self.request.user


def strava_connect(request: HttpRequest) -> HttpResponse:
    params = {
        "client_id": settings.STRAVA_CLIENT_ID,
        "redirect_uri": settings.STRAVA_REDIRECT_URI,
        "response_type": "code",
        "scope": "activity:read_all",
    }
    from urllib.parse import urlencode
    url = "https://www.strava.com/oauth/authorize?" + urlencode(params)
    return redirect(url)


def strava_callback(request: HttpRequest) -> HttpResponse:
    code = request.GET.get("code")
    if not code:
        messages.error(request, "Error al conectar con Strava.")
        return redirect("accounts:profile")

    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": settings.STRAVA_CLIENT_ID,
        "client_secret": settings.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=10)

    if response.status_code != 200:
        messages.error(request, "Error al obtener tokens de Strava.")
        return redirect("accounts:profile")

    data = response.json()
    from django.utils.dateformat import format
    from django.utils import timezone
    import datetime

    user = request.user
    user.strava_athlete_id = data["athlete"]["id"]
    user.strava_access_token = data["access_token"]
    user.strava_refresh_token = data["refresh_token"]
    user.strava_token_expires_at = timezone.datetime.fromtimestamp(
        data["expires_at"], tz=timezone.utc
    )
    user.save(update_fields=[
        "strava_athlete_id", "strava_access_token",
        "strava_refresh_token", "strava_token_expires_at"
    ])
    messages.success(request, "Cuenta Strava conectada correctamente.")
    return redirect("accounts:profile")


def strava_disconnect(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        user = request.user
        user.strava_athlete_id = None
        user.strava_access_token = ""
        user.strava_refresh_token = ""
        user.strava_token_expires_at = None
        user.save(update_fields=[
            "strava_athlete_id", "strava_access_token",
            "strava_refresh_token", "strava_token_expires_at"
        ])
        messages.success(request, "Cuenta Strava desconectada.")
    return redirect("accounts:profile")
