from django import forms
from apps.editions.models import Edition


class EditionForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = Edition
        fields = ["date", "name", "route_gpx", "status"]
