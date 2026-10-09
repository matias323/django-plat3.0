from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView, CreateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy

from core.models.user import User
from applications.role.models import RoleUser
from core.forms.user_form import AdminUserProfileForm, AdminPersonProfileForm, AdminUserRolesForm
from django.contrib.auth.forms import SetPasswordForm # Permite cambiar la clave sin requerir la contraseña antigua


from core.forms.user_form import AdminUserCreationForm

class UserCreateView(LoginRequiredMixin, CreateView):
    model = User
    form_class = AdminUserCreationForm
    template_name = 'core/user_form.html'
    success_url = reverse_lazy('core:user_list')

    def form_valid(self, form):
        # Ahora el formulario aceptará este argumento sin problemas
        self.object = form.save(commit=True, user_audit=self.request.user)
        
        messages.success(self.request, "Usuario creado exitosamente con sus roles y permisos asignados.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Por favor corrige los errores en el formulario de creación.")
        return super().form_invalid(form)

class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'core/user_list.html'
    context_object_name = 'usuarios'
    paginate_by = 15

    def get_queryset(self):
        # Optimizamos trayendo la relación con Person para evitar consultas N+1
        return User.objects.select_related('person').order_by('-date_joined')


class UserDetailUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'core/user_detail.html'

    def get_user_target(self):
        return get_object_or_404(User.objects.select_related('person'), pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = self.get_user_target()
        
        if 'profile_form' not in context:
            context['profile_form'] = AdminUserProfileForm(instance=target_user, prefix='user')
        if 'person_form' not in context:
            context['person_form'] = AdminPersonProfileForm(instance=target_user.person, prefix='person')
        if 'roles_form' not in context:
            context['roles_form'] = AdminUserRolesForm(user_target=target_user, prefix='roles')
        if 'password_form' not in context:
            # SetPasswordForm es ideal para que un admin cambie la clave de otro usuario sin saber la anterior
            context['password_form'] = SetPasswordForm(user=target_user, prefix='password')
            
        context['target_user'] = target_user
        return context

    def post(self, request, *args, **kwargs):
        target_user = self.get_user_target()
        action = request.POST.get('action')

        # 1. Actualizar Información de Cuenta (User) y Persona (Person)
        if action == 'update_info':
            profile_form = AdminUserProfileForm(request.POST, instance=target_user, prefix='user')
            person_form = AdminPersonProfileForm(request.POST, instance=target_user.person, prefix='person')
            
            if profile_form.is_valid() and person_form.is_valid():
                profile_form.save()
                person_obj = person_form.save(commit=False)
                person_obj.save(user=request.user) # Auditoría BaseModel
                
                messages.success(request, "Información de usuario actualizada exitosamente.")
                return redirect('core:user_detail', pk=target_user.pk)
            else:
                messages.error(request, "Corrige los errores en los formularios de información.")
                return self.render_to_response(self.get_context_data(profile_form=profile_form, person_form=person_form))

        # 2. Gestionar / Asignar Roles
        elif action == 'update_roles':
            roles_form = AdminUserRolesForm(request.POST, user_target=target_user, prefix='roles')
            if roles_form.is_valid():
                roles_form.save(user_audit=request.user)
                messages.success(request, "Roles actualizados exitosamente.")
                return redirect('core:user_detail', pk=target_user.pk)
            else:
                messages.error(request, "Error al actualizar los roles.")
                return self.render_to_response(self.get_context_data(roles_form=roles_form))

        # 3. Cambiar Contraseña (Administrador)
        elif action == 'change_password':
            password_form = SetPasswordForm(user=target_user, data=request.POST, prefix='password')
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "Contraseña modificada exitosamente.")
                return redirect('core:user_detail', pk=target_user.pk)
            else:
                messages.error(request, "Error al cambiar la contraseña. Verifica que coincidan.")
                return self.render_to_response(self.get_context_data(password_form=password_form))

        return redirect('core:user_detail', pk=target_user.pk)