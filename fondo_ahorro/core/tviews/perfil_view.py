from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import update_session_auth_hash
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.contrib import messages

# Importa el nuevo formulario personalizado
from core.forms.person_form import UserProfileForm, PersonProfileForm, CustomPasswordChangeForm, ChangeRoleForm
from applications.role.models import RoleUser, RoleApp

class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'core/perfil.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        session = getattr(self.request, 'user_session', None)
        
        if 'profile_form' not in context:
            context['profile_form'] = UserProfileForm(instance=user)
        if 'person_form' not in context:
            context['person_form'] = PersonProfileForm(instance=user.person)
        if 'password_form' not in context:
            # Pasamos 'user=user' al formulario personalizado de contraseña
            context['password_form'] = CustomPasswordChangeForm(user=user)
        
        if 'role_form' not in context:
            app_actual = session.app if session else None
            context['role_form'] = ChangeRoleForm(user=user, app=app_actual)
            
        context['active_session'] = session
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        session = getattr(request, 'user_session', None)
        action = request.POST.get('action')

        # 1. Actualizar Información Personal
        if action == 'update_profile':
            profile_form = UserProfileForm(request.POST, instance=user)
            person_form = PersonProfileForm(request.POST, instance=user.person)
            
            if profile_form.is_valid() and person_form.is_valid():
                profile_form.save()
                person_obj = person_form.save(commit=False)
                person_obj.save(user=user)
                
                messages.success(request, "Información personal actualizada exitosamente.")
                return redirect('core:perfil')
            else:
                messages.error(request, "Por favor corrige los errores en el formulario de perfil.")
                return self.render_to_response(self.get_context_data(
                    profile_form=profile_form, 
                    person_form=person_form
                ))

        # 2. Cambiar Contraseña (Usando el formulario personalizado)
        elif action == 'change_password':
            password_form = CustomPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user_obj = password_form.save()
                # Actualiza el hash de sesión para que no saque al usuario del sistema
                update_session_auth_hash(request, user_obj)
                messages.success(request, "Contraseña actualizada exitosamente.")
                return redirect('core:perfil')
            else:
                messages.error(request, "Error al cambiar la contraseña. Verifica los datos.")
                return self.render_to_response(self.get_context_data(password_form=password_form))

        # 3. Cambiar de Rol en la Sesión Actual
        elif action == 'change_role':
            app_actual = session.app if session else None
            role_form = ChangeRoleForm(request.POST, user=user, app=app_actual)
            
            if role_form.is_valid():
                nuevo_rol = role_form.cleaned_data['role']
                
                if session and app_actual:
                    tiene_rol = RoleUser.objects.filter(user=user, role=nuevo_rol, is_active=True).exists()
                    # rol_en_app = RoleApp.objects.filter(app=app_actual, role=nuevo_rol, is_active=True).exists()

                    # if tiene_rol and rol_en_app:
                    if tiene_rol:
                        session.role = nuevo_rol
                        session.save(update_fields=['role'])
                        messages.success(request, f"Rol cambiado exitosamente a: {nuevo_rol.name}")
                    else:
                        messages.error(request, "No tienes autorización para usar este rol en la aplicación actual.")
                else:
                    messages.error(request, "No se encontró una sesión activa válida.")
                
                return redirect('core:perfil')
            else:
                messages.error(request, "Selección de rol inválida.")
                return self.render_to_response(self.get_context_data(role_form=role_form))

        return redirect('core:perfil')