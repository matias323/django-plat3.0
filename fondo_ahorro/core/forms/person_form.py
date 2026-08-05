from django import forms
from core.models.person import Person

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            'rut',
            'dv',
            'first_name',
            'second_name',
            'last_name_1',
            'last_name_2',
            'birth_date',
            'person_type',
        ]
        labels = {
            'rut': 'RUT',
            'dv': 'DV',
            'first_name': 'Primer Nombre',
            'second_name': 'Segundo Nombre',
            'last_name_1': 'Primer Apellido',
            'last_name_2': 'Segundo Apellido',
            'birth_date': 'Fecha de Nacimiento',
            'person_type': 'Tipo de Persona',
        }
        widgets = {
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 12345678', 'id': 'id_rut'}),
            'dv': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'K', 'maxlength': '1', 'id': 'id_dv'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'second_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name_1': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name_2': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'person_type': forms.Select(attrs={'class': 'form-select'}),
        }