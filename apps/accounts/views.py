import logging
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import View, FormView, UpdateView
from django.contrib import messages
from django.http import HttpRequest, HttpResponse

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
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get("next", "/"))
        return render(request, self.template_name, {"error": "Credenciales incorrectas"})


class LogoutView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        return redirect("home")


from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView


class ProfileView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        import secrets
        from django.conf import settings as conf
        from apps.accounts.services.strava import StravaClient
        # Genera un token CSRF para el flujo OAuth y lo guarda en sesión
        state = secrets.token_urlsafe(24)
        self.request.session["strava_oauth_state"] = state
        ctx["strava_auth_url"] = StravaClient.get_auth_url(
            redirect_uri=conf.STRAVA_REDIRECT_URI,
            state=state,
        )
        return ctx


class StravaDisconnectWebView(LoginRequiredMixin, View):
    """POST /accounts/strava/disconnect/ — Desconecta Strava desde la web."""

    def post(self, request: HttpRequest) -> HttpResponse:
        from apps.accounts.services.strava import StravaClient
        if request.user.strava_connected:
            StravaClient(request.user).revoke_token()
            messages.success(request, "Cuenta de Strava desconectada.")
        return redirect("accounts:profile")


class StravaCallbackView(LoginRequiredMixin, View):
    """GET /accounts/strava/callback/?code=...  — Recibe el code de Strava y guarda tokens."""

    def get(self, request: HttpRequest) -> HttpResponse:
        from django.conf import settings as conf
        from apps.accounts.services.strava import StravaClient, StravaError
        import datetime

        code = request.GET.get("code")
        error = request.GET.get("error")
        returned_state = request.GET.get("state", "")

        if error or not code:
            messages.error(request, "Conexión con Strava cancelada o denegada.")
            return redirect("accounts:profile")

        # Verificar CSRF: el state debe coincidir con el guardado en sesión (web)
        # o en caché (móvil que usa el flujo web como redirect).
        from django.core.cache import cache as django_cache
        cache_key = f"strava_oauth_state_{request.user.pk}"
        expected_state = (
            request.session.pop("strava_oauth_state", None)
            or django_cache.get(cache_key)
        )
        if expected_state and django_cache.get(cache_key):
            django_cache.delete(cache_key)
        if not expected_state or returned_state != expected_state:
            logger.warning(
                "Strava OAuth state mismatch para user=%s (posible CSRF)",
                request.user.pk,
            )
            messages.error(request, "Error de seguridad en la conexión con Strava. Inténtalo de nuevo.")
            return redirect("accounts:profile")

        try:
            payload = StravaClient.exchange_code(
                code=code,
                redirect_uri=conf.STRAVA_REDIRECT_URI,
            )
        except StravaError as exc:
            logger.warning("Strava OAuth callback error: %s", exc)
            messages.error(request, "No se pudo conectar con Strava. Inténtalo de nuevo.")
            return redirect("accounts:profile")

        from django.utils import timezone as tz
        athlete = payload.get("athlete", {})
        user = request.user
        user.strava_athlete_id = athlete.get("id")
        user.strava_access_token = payload.get("access_token", "")
        user.strava_refresh_token = payload.get("refresh_token", "")
        expires_at = payload.get("expires_at")
        if expires_at:
            user.strava_token_expires_at = tz.make_aware(
                datetime.datetime.fromtimestamp(expires_at),
                tz.get_current_timezone(),
            )
        user.save(update_fields=[
            "strava_athlete_id", "strava_access_token",
            "strava_refresh_token", "strava_token_expires_at",
        ])
        messages.success(request, "Cuenta de Strava conectada correctamente.")
        return redirect("accounts:profile")


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")


class CustomPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"
