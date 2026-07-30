from django import forms


class LoginForm(forms.Form):
    rut = forms.CharField(
        label="RUT / Identificación",
        max_length=12,
        widget=forms.TextInput(
            attrs={
                "id": "rut_input",  # Identificador para JavaScript
                "class": "form-control",
                "placeholder": "12.345.678-K",
                "autocomplete": "off",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        ),
    )