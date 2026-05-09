from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("editions/", views.EditionListView.as_view(), name="edition_list"),
    path("editions/new/", views.EditionCreateView.as_view(), name="edition_create"),
    path("editions/<int:pk>/edit/", views.EditionUpdateView.as_view(), name="edition_edit"),
    path("editions/<int:pk>/delete/", views.EditionDeleteView.as_view(), name="edition_delete"),
    path("editions/<int:pk>/", views.EditionDetailView.as_view(), name="edition_detail"),
    path("editions/<int:pk>/publish/", views.publish_results, name="publish_results"),
    path("editions/<int:pk>/media/add/", views.media_add, name="media_add"),
    path("variants/", views.RouteVariantListView.as_view(), name="variant_list"),
    path("variants/new/", views.RouteVariantCreateView.as_view(), name="variant_create"),
    path("media/<int:pk>/delete/", views.media_delete, name="media_delete"),
    path("activities/<int:pk>/validate/", views.override_validation, name="override_validation"),
]
