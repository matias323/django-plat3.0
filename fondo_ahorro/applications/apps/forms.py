from django import forms
from applications.apps.models import App
from applications.role.models import Role, RoleApp

class AppAdminForm(forms.ModelForm):
    # Campo opcional para asignar roles directamente al crear/editar la app
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2'}), # O tu clase CSS preferida
        label="Roles con Acceso"
    )

    class Meta:
        model = App
        fields = ['name', 'url', 'has_daughter', 'order', 'father_app', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'url': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'father_app': forms.Select(attrs={'class': 'form-select'}),
            'has_daughter': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando una App existente, preseleccionamos los roles que ya tiene en RoleApp
        if self.instance and self.instance.pk:
            roles_actuales = RoleApp.objects.filter(
                app=self.instance, 
                is_active=True
            ).values_list('role_id', flat=True)
            self.fields['roles'].initial = roles_actuales

    def save(self, commit=True, user=None):
        # Guardamos la App
        app = super().save(commit=commit)
        
        if commit and app:
            roles_seleccionados = self.cleaned_data.get('roles', [])
            
            # Gestionar RoleApp y activar/desactivar según corresponda
            roles_existentes = RoleApp.objects.filter(app=app)
            roles_existentes_ids = roles_existentes.values_list('role_id', flat=True)

            # 1. Crear los nuevos RoleApp (Esto disparará automáticamente el método save() 
            # de RoleApp que programamos arriba y creará los UserPermission correspondientes)
            for role in roles_seleccionados:
                if role.id not in roles_existentes_ids:
                    RoleApp.objects.create(
                        app=app,
                        role=role,
                        is_active=True,
                        user_create=user,
                        user_update=user
                    )
                else:
                    # Si ya existía pero estaba inactivo, lo reactivamos
                    RoleApp.objects.filter(app=app, role=role).update(is_active=True, user_update=user)

            # 2. Desactivar los roles que fueron desmarcados
            RoleApp.objects.filter(app=app).exclude(role__in=roles_seleccionados).update(is_active=False, user_update=user)

        return app