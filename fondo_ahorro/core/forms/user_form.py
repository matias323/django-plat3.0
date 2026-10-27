from django import forms
from django.contrib.auth.hashers import make_password
from core.models.user import User
from core.models.person import Person, PersonType
from applications.role.models import Role, RoleUser, RoleApp, Permission
from core.models.user import UserPermission



class AdminUserProfileForm(forms.ModelForm):
    """Formulario para que el administrador edite el username y el email del usuario"""
    class Meta:
        model = User
        fields = ['username', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class AdminUserPermissionsForm(forms.Form):
    """Formulario para gestionar o actualizar los permisos específicos de UserPermission del usuario filtrado por rol activo"""
    
    def __init__(self, *args, **kwargs):
        self.user_target = kwargs.pop('user_target', None)
        self.selected_role_id = kwargs.pop('selected_role_id', None)
        super().__init__(*args, **kwargs)
        
        self.permission_rows = []
        
        if self.user_target:
            # 1. Obtenemos únicamente los IDs de los roles que el usuario tiene activos en RoleUser
            roles_activos_ids = RoleUser.objects.filter(
                user=self.user_target, 
                is_active=True
            ).values_list('role_id', flat=True)

            # 2. Consultamos los permisos asegurando que pertenezcan a roles con is_active=True
            user_perms_qs = UserPermission.objects.filter(
                user=self.user_target,
                role_id__in=roles_activos_ids
            ).select_related('app', 'role', 'permission')
            
            # 3. Si se seleccionó un rol específico en el filtro de la vista, lo aplicamos también
            if self.selected_role_id and self.selected_role_id.isdigit():
                user_perms_qs = user_perms_qs.filter(role_id=int(self.selected_role_id))
            
            for up in user_perms_qs:
                field_perm_name = f'perm_{up.pk}'
                field_active_name = f'active_{up.pk}'
                
                self.fields[field_perm_name] = forms.ModelChoiceField(
                    queryset=Permission.objects.all(),
                    initial=up.permission_id,
                    widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
                    required=False
                )
                
                self.fields[field_active_name] = forms.BooleanField(
                    initial=getattr(up, 'is_active', True),
                    required=False,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
                
                self.permission_rows.append({
                    'up': up,
                    'perm_field': self[field_perm_name],
                    'active_field': self[field_active_name],
                    'perm_field_name': field_perm_name,
                    'active_field_name': field_active_name,
                })

    def save(self, user_audit=None):
        if not self.user_target:
            return
            
        for row in self.permission_rows:
            up_obj = row['up']
            perm_name = row['perm_field_name']
            active_name = row['active_field_name']
            
            new_permission = self.cleaned_data.get(perm_name)
            is_active_status = self.cleaned_data.get(active_name, True)
            
            if new_permission:
                up_obj.permission = new_permission
                
            if hasattr(up_obj, 'is_active'):
                up_obj.is_active = is_active_status
                
            try:
                up_obj.save(user=user_audit)
            except TypeError:
                up_obj.save()

class AdminPersonProfileForm(forms.ModelForm):
    """Formulario para editar los datos personales de la persona asociada"""
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


class AdminUserCreationForm(forms.ModelForm):
    rut = forms.IntegerField(label="RUT (sin dígito verificador)", widget=forms.NumberInput(attrs={'class': 'form-control'}))
    dv = forms.CharField(label="Dígito Verificador", max_length=1, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label="Primer Nombre", max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    second_name = forms.CharField(label="Segundo Nombre", max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name_1 = forms.CharField(label="Primer Apellido", max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name_2 = forms.CharField(label="Segundo Apellido", max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    birth_date = forms.DateField(label="Fecha de Nacimiento", widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    person_type = forms.ModelChoiceField(queryset=PersonType.objects.all(), label="Tipo de Persona", required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    email = forms.EmailField(label="Correo Electrónico", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2', 'size': '6'}),
        label="Roles Iniciales"
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if Person.objects.filter(rut=rut).exists():
            raise forms.ValidationError("Ya existe una persona registrada con este RUT.")
        return rut

    def save(self, commit=True, user_audit=None):
        cleaned_data = self.cleaned_data
        
        # 1. Creamos el objeto Person (Hereda de BaseModel, sí acepta user=...)
        person = Person(
            rut=cleaned_data['rut'],
            dv=cleaned_data['dv'].upper(),
            first_name=cleaned_data['first_name'],
            second_name=cleaned_data.get('second_name'),
            last_name_1=cleaned_data['last_name_1'],
            last_name_2=cleaned_data.get('last_name_2'),
            birth_date=cleaned_data['birth_date'],
            person_type=cleaned_data.get('person_type'),
        )
        if commit:
            person.save(user=user_audit)

        # 2. Creamos el objeto User (Hereda de AbstractUser, NO acepta user= en el save)
        user = User(
            username=cleaned_data['username'],
            email=cleaned_data['email'],
            person=person,
            is_active=True,
        )
        user.set_password(cleaned_data['password'])
        if commit:
            user.save() # <-- Se llama de forma estándar sin argumentos extra

        # 3. Asignación de Roles y Propagación Automática de UserPermission
        roles_seleccionados = cleaned_data.get('roles', [])
        if roles_seleccionados and commit:
            permiso_default = Permission.objects.filter(id=1).first() or Permission.objects.first()

            for role in roles_seleccionados:
                # A. Creamos la relación RoleUser (Hereda de BaseModel, sí acepta user=...)
                role_user = RoleUser(
                    user=user,
                    role=role,
                    is_active=True,
                )
                role_user.save(user=user_audit)

                # B. Propagación automática de UserPermission (Hereda de BaseModel, sí acepta user=...)
                if permiso_default:
                    apps_del_rol = RoleApp.objects.filter(role=role, is_active=True).values_list('app_id', flat=True)
                    for app_id in apps_del_rol:
                        user_perm, created = UserPermission.objects.get_or_create(
                            user=user,
                            app_id=app_id,
                            role=role,
                            defaults={
                                'permission': permiso_default,
                                'is_active': True,
                            }
                        )
                        if not created:
                            user_perm.save(user=user_audit)

        return user


class AdminUserRolesForm(forms.Form):
    """Formulario para gestionar los roles asignados al usuario (RoleUser) con casillas tipo tarjeta"""
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        # Cambiamos a CheckboxSelectMultiple para un diseño visual basado en tarjetas
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Roles Asignados"
    )

    def __init__(self, *args, **kwargs):
        self.user_target = kwargs.pop('user_target', None)
        super().__init__(*args, **kwargs)
        if self.user_target:
            roles_actuales = RoleUser.objects.filter(
                user=self.user_target, 
                is_active=True
            ).values_list('role_id', flat=True)
            self.fields['roles'].initial = roles_actuales

    def save(self, user_audit=None):
        if not self.user_target:
            return
        
        roles_seleccionados = self.cleaned_data.get('roles', [])
        roles_existentes = RoleUser.objects.filter(user=self.user_target)
        roles_existentes_ids = roles_existentes.values_list('role_id', flat=True)

        # 1. Crear o activar nuevos roles
        for role in roles_seleccionados:
            if role.id not in roles_existentes_ids:
                RoleUser.objects.create(
                    user=self.user_target,
                    role=role,
                    is_active=True,
                    user_create=user_audit,
                    user_update=user_audit
                )
            else:
                RoleUser.objects.filter(user=self.user_target, role=role).update(is_active=True, user_update=user_audit)

        # 2. Desactivar los roles que fueron desmarcados
        RoleUser.objects.filter(user=self.user_target).exclude(role__in=roles_seleccionados).update(is_active=False, user_update=user_audit)