import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, View, TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from apps.editions.models import Edition
from apps.participations.models import Participation, StravaActivity
from apps.classifications.models import Classification, get_category
from .forms import EditionForm

logger = logging.getLogger(__name__)


class StaffRequiredMixin(LoginRequiredMixin):
    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class DashboardHomeView(StaffRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["editions"] = Edition.objects.all()[:10]
        ctx["total_users"] = Participation.objects.values("user").distinct().count()
        return ctx


class EditionListView(StaffRequiredMixin, ListView):
    model = Edition
    template_name = "dashboard/edition_list.html"
    context_object_name = "editions"


class EditionCreateView(StaffRequiredMixin, CreateView):
    model = Edition
    form_class = EditionForm
    template_name = "dashboard/edition_form.html"
    success_url = reverse_lazy("dashboard:edition_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        edition = self.object
        if edition.route_gpx:
            self._parse_gpx(edition)
        return response

    def _parse_gpx(self, edition: Edition):
        import gpxpy
        try:
            with edition.route_gpx.open("rb") as f:
                gpx = gpxpy.parse(f)
            coords = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        coords.append([point.longitude, point.latitude])
            edition.route_geojson = {"type": "LineString", "coordinates": coords}
            edition.route_distance_km = round(gpx.length_2d() / 1000, 2)
            edition.save(update_fields=["route_geojson", "route_distance_km"])
        except Exception:
            logger.exception("Error parsing GPX for edition %s", edition.pk)


class EditionDetailView(StaffRequiredMixin, DetailView):
    model = Edition
    template_name = "dashboard/edition_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["participations"] = (
            self.object.participations
            .select_related("user", "strava_activity", "classification")
            .order_by("registered_at")
        )
        ctx["media_items"] = self.object.media.all()
        return ctx


@staff_member_required
def publish_results(request, pk):
    edition = get_object_or_404(Edition, pk=pk)
    if request.method == "POST":
        _recalculate_positions(edition)
        edition.status = Edition.STATUS_PUBLISHED
        edition.save(update_fields=["status"])
        messages.success(request, f"Resultados de {edition.name} publicados.")
    return redirect("dashboard:edition_detail", pk=pk)


@staff_member_required
def override_validation(request, pk):
    activity = get_object_or_404(StravaActivity, pk=pk)
    if request.method == "POST":
        activity.is_valid = not activity.is_valid
        activity.save(update_fields=["is_valid"])
        _sync_classification(activity.participation)
        messages.success(request, "Validación actualizada.")
    return redirect("dashboard:edition_detail", pk=activity.participation.edition_id)


def _recalculate_positions(edition: Edition):
    valid = list(
        StravaActivity.objects.filter(
            participation__edition=edition, is_valid=True
        ).select_related("participation__user")
        .order_by("elapsed_time_seconds")
    )
    category_counters: dict[str, int] = {}
    for pos, activity in enumerate(valid, start=1):
        participation = activity.participation
        user = participation.user
        if not user.birth_date:
            category = "open"
        else:
            category = get_category(user.birth_date, edition.date)
        category_counters[category] = category_counters.get(category, 0) + 1
        Classification.objects.update_or_create(
            participation=participation,
            defaults={
                "time_seconds": activity.elapsed_time_seconds,
                "category": category,
                "position_overall": pos,
                "position_category": category_counters[category],
            },
        )


def _sync_classification(participation: Participation):
    try:
        activity = participation.strava_activity
    except StravaActivity.DoesNotExist:
        Classification.objects.filter(participation=participation).delete()
        return
    if not activity.is_valid:
        Classification.objects.filter(participation=participation).delete()
    else:
        _recalculate_positions(participation.edition)


# ─── Media management ────────────────────────────────────────────────────────

@staff_member_required
def media_add(request, pk):
    from apps.editions.models import EditionMedia
    edition = get_object_or_404(Edition, pk=pk)
    if request.method == "POST":
        media_type = request.POST.get("media_type")
        caption = request.POST.get("caption", "")
        order = int(request.POST.get("order", 0))
        if media_type == EditionMedia.TYPE_PHOTO and request.FILES.get("photo"):
            EditionMedia.objects.create(
                edition=edition,
                media_type=EditionMedia.TYPE_PHOTO,
                photo=request.FILES["photo"],
                caption=caption,
                order=order,
            )
            messages.success(request, "Foto añadida.")
        elif media_type == EditionMedia.TYPE_VIDEO:
            video_url = request.POST.get("video_url", "")
            if video_url:
                EditionMedia.objects.create(
                    edition=edition,
                    media_type=EditionMedia.TYPE_VIDEO,
                    video_url=video_url,
                    caption=caption,
                    order=order,
                )
                messages.success(request, "Vídeo añadido.")
            else:
                messages.error(request, "Indica una URL de vídeo.")
        else:
            messages.error(request, "Datos de media incompletos.")
    return redirect("dashboard:edition_detail", pk=pk)


@staff_member_required
def media_delete(request, pk):
    from apps.editions.models import EditionMedia
    media = get_object_or_404(EditionMedia, pk=pk)
    edition_pk = media.edition_id
    if request.method == "POST":
        if media.photo:
            media.photo.delete(save=False)
        media.delete()
        messages.success(request, "Media eliminada.")
    return redirect("dashboard:edition_detail", pk=edition_pk)
