from django.contrib.auth.models import AbstractUser
from django.db import models


class UserProfile(AbstractUser):
    full_name = models.CharField(max_length=200, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    club = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"

    def __str__(self) -> str:
        return self.full_name or self.username
