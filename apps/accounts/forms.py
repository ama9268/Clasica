from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile


class RegisterForm(UserCreationForm):
    full_name = forms.CharField(max_length=200, label="Nombre completo")
    birth_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha de nacimiento",
    )
    club = forms.CharField(max_length=150, required=False, label="Club / Equipo")

    class Meta:
        model = UserProfile
        fields = ["username", "email", "full_name", "birth_date", "club", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data["full_name"]
        user.birth_date = self.cleaned_data["birth_date"]
        user.club = self.cleaned_data.get("club", "")
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    birth_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        label="Fecha de nacimiento",
    )

    class Meta:
        model = UserProfile
        fields = ["full_name", "birth_date", "club", "photo"]
