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


from django import forms
from django.contrib.auth import update_session_auth_hash
from core.models.user import User
from core.models.person import Person, PersonContact


from applications.role.models import Role, RoleUser, RoleApp

class UserProfileForm(forms.ModelForm):
    # El email ahora pertenece directamente al modelo User
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class PersonProfileForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['first_name', 'second_name', 'last_name_1', 'last_name_2', 'birth_date']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'second_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name_1': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name_2': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class CustomPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label="Contraseña Actual",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password1 = forms.CharField(
        label="Nueva Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password2 = forms.CharField(
        label="Confirmar Nueva Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        # Usamos tu método personalizado de validación definido en el modelo User
        if not self.user.validate_password(old_password):
            raise forms.ValidationError("La contraseña actual es incorrecta.")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las nuevas contraseñas no coinciden.")
        return cleaned_data

    def save(self):
        new_password = self.cleaned_data.get("new_password1")
        # Si usas set_password nativo de AbstractUser:
        self.user.set_password(new_password)
        self.user.save()
        return self.user

class ChangeRoleForm(forms.Form):
    role = forms.ModelChoiceField(
        queryset=None,
        label="Seleccionar Rol",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        app = kwargs.pop('app', None)
        super().__init__(*args, **kwargs)
        
        if user and app:
            # Obtener los roles permitidos para este usuario en esta app desde UserPermission
            from applications.role.models import RoleUser
            roles_ids = RoleUser.objects.filter(
                user=user, 
                # app=app, 
                is_active=True
            ).values_list('role_id', flat=True)
            
            from applications.role.models import Role
            self.fields['role'].queryset = Role.objects.filter(id__in=roles_ids, is_active=True)