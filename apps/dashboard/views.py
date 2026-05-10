import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone

from apps.editions.models import Edition, RouteVariant
from apps.participations.models import Participation, Activity
from apps.classifications.models import Classification, get_category
from apps.editions.utils import parse_gpx_to_geometry_and_elevation
from .forms import EditionForm, RouteVariantForm

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
            geom, distance, ele_profile = parse_gpx_to_geometry_and_elevation(edition.route_gpx)
            if geom:
                edition.route_geometry = geom
                edition.route_distance_km = distance
                edition.elevation_profile = ele_profile
                edition.save(update_fields=["route_geometry", "route_distance_km", "elevation_profile"])
        return response


class EditionUpdateView(StaffRequiredMixin, UpdateView):
    model = Edition
    form_class = EditionForm
    template_name = "dashboard/edition_form.html"
    success_url = reverse_lazy("dashboard:edition_list")

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().has_started:
            messages.error(request, "No se puede editar una edición que ya ha comenzado.")
            return redirect("dashboard:edition_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        edition = self.object
        if edition.route_gpx and "route_gpx" in form.changed_data:
            geom, distance, ele_profile = parse_gpx_to_geometry_and_elevation(edition.route_gpx)
            if geom:
                edition.route_geometry = geom
                edition.route_distance_km = distance
                edition.elevation_profile = ele_profile
                edition.save(update_fields=["route_geometry", "route_distance_km", "elevation_profile"])
        return response


class EditionDeleteView(StaffRequiredMixin, DeleteView):
    model = Edition
    template_name = "dashboard/edition_confirm_delete.html"
    success_url = reverse_lazy("dashboard:edition_list")

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().has_started:
            messages.error(request, "No se puede eliminar una edición que ya ha comenzado.")
            return redirect("dashboard:edition_list")
        return super().dispatch(request, *args, **kwargs)


class RouteVariantListView(StaffRequiredMixin, ListView):
    model = RouteVariant
    template_name = "dashboard/variant_list.html"
    context_object_name = "variants"


class RouteVariantCreateView(StaffRequiredMixin, CreateView):
    model = RouteVariant
    form_class = RouteVariantForm
    template_name = "dashboard/variant_form.html"
    success_url = reverse_lazy("dashboard:variant_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        variant = self.object
        if variant.route_gpx:
            geom, distance, ele_profile = parse_gpx_to_geometry_and_elevation(variant.route_gpx)
            if geom:
                variant.route_geometry = geom
                variant.route_distance_km = distance
                variant.elevation_profile = ele_profile
                variant.save(update_fields=["route_geometry", "route_distance_km", "elevation_profile"])
        return response


class EditionDetailView(StaffRequiredMixin, DetailView):
    model = Edition
    template_name = "dashboard/edition_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["participations"] = (
            self.object.participations
            .select_related("user", "activity", "classification")
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
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == "POST":
        activity.is_valid = not activity.is_valid
        activity.save(update_fields=["is_valid"])
        _sync_classification(activity.participation)
        messages.success(request, "Validación actualizada.")
    return redirect("dashboard:edition_detail", pk=activity.participation.edition_id)


def _recalculate_positions(edition: Edition):
    valid = list(
        Activity.objects.filter(
            participation__edition=edition, is_valid=True
        ).select_related("participation__user")
        .order_by("elapsed_time_seconds")
    )
    category_counters: dict[str, int] = {}
    for pos, activity in enumerate(valid, start=1):
        participation = activity.participation
        user = participation.user
        category = get_category(user.birth_date, edition.date) if user.birth_date else "open"
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
        activity = participation.activity
    except Activity.DoesNotExist:
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
                edition=edition, media_type=EditionMedia.TYPE_PHOTO,
                photo=request.FILES["photo"], caption=caption, order=order,
            )
            messages.success(request, "Foto añadida.")
        elif media_type == EditionMedia.TYPE_VIDEO:
            video_url = request.POST.get("video_url", "")
            if video_url:
                EditionMedia.objects.create(
                    edition=edition, media_type=EditionMedia.TYPE_VIDEO,
                    video_url=video_url, caption=caption, order=order,
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
