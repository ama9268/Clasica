from django import forms
from apps.editions.models import Edition, RouteVariant


class RouteVariantForm(forms.ModelForm):
    class Meta:
        model = RouteVariant
        fields = ["name", "description", "route_gpx"]


class EditionForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = Edition
        fields = ["date", "start_time", "name", "route_variant", "route_gpx", "status"]

    def clean_date(self):
        date = self.cleaned_data.get('date')
        from django.utils import timezone
        
        # Permitir editar una edición antigua sin que salte error por su propia fecha
        if self.instance and self.instance.pk and self.instance.date == date:
            return date
            
        # No permitir crear o cambiar la fecha a un día del pasado
        if date and date < timezone.now().date():
            raise forms.ValidationError("La fecha de la edición no puede ser en el pasado.")
            
        return date
