from django.urls import path
from . import views

app_name = "editions"

urlpatterns = [
    path("<int:pk>/", views.EditionDetailView.as_view(), name="detail"),
    path("<int:pk>/register/", views.edition_register, name="register"),
]
