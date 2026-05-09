import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, View, TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from apps.editions.models import Edition
from apps.participations.models import Participation
from apps.classifications.models import Classification
from apps.editions.services.aemet import get_weather_forecast_for_edition

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    """Página de inicio — pública."""
    template_name = "public/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next_edition"] = Edition.objects.filter(status=Edition.STATUS_OPEN).first()
        ctx["last_editions"] = Edition.objects.filter(status=Edition.STATUS_PUBLISHED)[:5]
        return ctx


class EditionListView(LoginRequiredMixin, ListView):
    """Lista de ediciones — solo ciclistas registrados."""
    model = Edition
    template_name = "public/edition_list.html"
    context_object_name = "editions"
    paginate_by = 20


class EditionDetailView(LoginRequiredMixin, DetailView):
    """Detalle de edición — solo ciclistas registrados."""
    model = Edition
    template_name = "public/edition_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        edition = self.object

        # Todos los inscritos
        ctx["participations"] = (
            edition.participations
            .select_related("user", "strava_activity", "classification")
            .order_by("registered_at")
        )

        # Clasificación (si resultados publicados)
        ctx["classifications"] = (
            Classification.objects.filter(
                participation__edition=edition,
                participation__strava_activity__is_valid=True,
            )
            .select_related("participation__user")
            .order_by("position_overall")
            if edition.results_published else []
        )

        # Participación del usuario actual
        if self.request.user.is_authenticated:
            ctx["user_participation"] = (
                Participation.objects.filter(user=self.request.user, edition=edition)
                .select_related("strava_activity", "classification")
                .first()
            )

        # Media (fotos y vídeos)
        ctx["media_photos"] = edition.media.filter(media_type="photo").order_by("order")
        ctx["media_videos"] = edition.media.filter(media_type="video").order_by("order")

        # Weather forecast (AEMET)
        ctx["weather"] = get_weather_forecast_for_edition(edition.date)

        return ctx


class GeneralClassificationView(LoginRequiredMixin, TemplateView):
    """Clasificación general — solo ciclistas registrados."""
    template_name = "public/general_classification.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Count, Q
        ctx["stats"] = (
            Participation.objects
            .values("user__pk", "user__full_name", "user__username", "user__club")
            .annotate(
                total_participations=Count("id"),
                total_valid=Count(
                    "strava_activity",
                    filter=Q(strava_activity__is_valid=True)
                ),
            )
            .order_by("-total_valid", "-total_participations")
        )
        return ctx


class PublicProfileView(LoginRequiredMixin, TemplateView):
    """Perfil público — solo ciclistas registrados."""
    template_name = "public/user_profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.accounts.models import UserProfile
        user = get_object_or_404(UserProfile, pk=self.kwargs["pk"])
        ctx["profile"] = user
        ctx["participations"] = (
            Participation.objects.filter(user=user)
            .select_related("edition", "strava_activity", "classification")
            .order_by("-edition__date")
        )
        return ctx


class LiveTrackingView(LoginRequiredMixin, TemplateView):
    """Mapa en directo — solo ciclistas registrados y en horario de ruta."""
    template_name = "public/live_tracking.html"

    def dispatch(self, request, *args, **kwargs):
        edition = get_object_or_404(Edition, pk=self.kwargs["edition_id"])
        if not edition.is_live and not request.user.is_staff:
            messages.warning(request, "El seguimiento en directo solo está disponible durante el horario de la ruta.")
            return redirect("edition_detail", pk=edition.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["edition"] = get_object_or_404(Edition, pk=self.kwargs["edition_id"])
        return ctx


def edition_register(request, pk):
    if not request.user.is_authenticated:
        return redirect(f"/accounts/login/?next=/editions/{pk}/register/")
    edition = get_object_or_404(Edition, pk=pk)
    if not edition.is_registration_open:
        messages.error(request, "Las inscripciones para esta edición están cerradas.")
        return redirect("edition_detail", pk=pk)
    _, created = Participation.objects.get_or_create(user=request.user, edition=edition)
    if created:
        messages.success(request, f"Te has inscrito en {edition.name}. ¡Nos vemos el miércoles!")
    else:
        messages.info(request, "Ya estabas inscrito en esta edición.")
    # Volver a la página de origen o al detalle de la edición
    return redirect(request.META.get("HTTP_REFERER", f"/editions/{pk}/"))
