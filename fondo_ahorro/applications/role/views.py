from django.shortcuts import render

# Create your views here.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages

from .models import Role, RoleApp, RoleUser
from .forms import RoleForm

class RoleListView(LoginRequiredMixin, ListView):
    model = Role
    template_name = 'role/role_list.html'
    context_object_name = 'roles'
    paginate_by = 15

    def get_queryset(self):
        # Muestra todos los roles ordenados por ID descendente
        return Role.objects.all().order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Gestión de Roles"
        context['form'] = RoleForm() # Para el modal o formulario de creación rápida
        return context

    def post(self, request, *args, **kwargs):
        """Acción para activar/desactivar un rol rápidamente desde la tabla"""
        role_id = request.POST.get('role_id')
        if role_id:
            role = get_object_or_404(Role, id=role_id)
            role.is_active = not role.is_active
            role.save(user=request.user) # Pasa el usuario para actualizar los campos de auditoría BaseModel
            
            estado_txt = "activado" if role.is_active else "desactivado"
            messages.success(request, f"El rol '{role.name}' ha sido {estado_txt} correctamente.")
        
        return redirect('role:role_list')


class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'role/role_form.html'
    success_url = reverse_lazy('role:role_list')

    def form_valid(self, form):
        # Guardamos pasando el usuario autenticado para que BaseModel registre user_create y user_update
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        messages.success(self.request, "Rol creado exitosamente.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Nuevo Rol"
        return context


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'role/role_form.html'
    success_url = reverse_lazy('role:role_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        messages.success(self.request, "Rol actualizado exitosamente.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Editar Rol: {self.object.name}"
        return context

class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'role/role_form.html'
    success_url = reverse_lazy('core:role_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Editar Rol: {self.object.name}"
        # Cargamos las relaciones asociadas a este rol
        context['role_apps'] = RoleApp.objects.filter(role=self.object).select_related('app')
        context['role_users'] = RoleUser.objects.filter(role=self.object).select_related('user')
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # 1. Validar si se está alternando el estado de una App asociada (RoleApp)
        role_app_id = request.POST.get('role_app_id')
        if role_app_id:
            role_app = get_object_or_404(RoleApp, id=role_app_id, role=self.object)
            role_app.is_active = not role_app.is_active
            role_app.save(user=request.user)  # Mantiene la auditoría de BaseModel
            estado = "activada" if role_app.is_active else "desactivada"
            messages.success(request, f"La app '{role_app.app.name}' ha sido {estado} para este rol.")
            return redirect('role:role_update', pk=self.object.pk)

        # 2. Validar si se está alternando el estado de un Usuario asociado (RoleUser)
        role_user_id = request.POST.get('role_user_id')
        if role_user_id:
            role_user = get_object_or_404(RoleUser, id=role_user_id, role=self.object)
            role_user.is_active = not role_user.is_active
            role_user.save(user=request.user)  # Mantiene la auditoría de BaseModel
            estado = "activado" if role_user.is_active else "desactivado"
            messages.success(request, f"El acceso del usuario ha sido {estado}.")
            return redirect('role:role_update', pk=self.object.pk)

        # 3. Flujo normal: Guardar los cambios del formulario principal del Rol
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        messages.success(self.request, "Rol actualizado exitosamente.")
        return redirect(self.success_url)