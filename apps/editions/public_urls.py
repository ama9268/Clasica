from django.urls import path
from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("editions/", views.EditionListView.as_view(), name="edition_list"),
    path("editions/<int:pk>/", views.EditionDetailView.as_view(), name="edition_detail"),
    path("clasificacion/", views.GeneralClassificationView.as_view(), name="general_classification"),
    path("perfil/<int:pk>/", views.PublicProfileView.as_view(), name="public_profile"),
    path("live/<int:edition_id>/", views.LiveTrackingView.as_view(), name="live_tracking"),
]
