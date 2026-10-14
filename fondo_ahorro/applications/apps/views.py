from django.shortcuts import render, redirect

# Create your views here.
from django.views.generic import CreateView, ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from applications.apps.models import App
from applications.apps.forms import AppAdminForm 

class AppCreateView(LoginRequiredMixin, CreateView):
    model = App
    form_class = AppAdminForm
    template_name = 'apps/app_form.html'
    success_url = reverse_lazy('apps:list') 

    def form_valid(self, form):
        # Guardamos pasando el usuario actual para que el BaseModel y RoleApp registren la auditoría
        form.instance.user_create = self.request.user
        form.instance.user_update = self.request.user
        
        self.object = form.save(commit=True, user=self.request.user)
        
        messages.success(self.request, "Aplicación creada y permisos propagados exitosamente.")
        return redirect(self.success_url)


class AppListView(LoginRequiredMixin, ListView):
    model = App
    template_name = 'apps/app_list.html'
    context_object_name = 'apps'
    paginate_by = 15 

    def get_queryset(self):
        return App.objects.select_related('father_app').order_by('order', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Listado de Aplicaciones"
        return context


class AppUpdateView(LoginRequiredMixin, UpdateView):
    model = App
    form_class = AppAdminForm
    template_name = 'apps/app_form.html'  # Reutilizamos el mismo template HTML de creación/edición
    success_url = reverse_lazy('apps:list')

    def form_valid(self, form):
        # Actualizamos el usuario modificador para respetar la auditoría del BaseModel
        form.instance.user_update = self.request.user
        
        # Guardamos la aplicación y procesamos los roles seleccionados pasándole el usuario
        self.object = form.save(commit=True, user=self.request.user)
        
        messages.success(self.request, "Aplicación y roles actualizados exitosamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Por favor corrige los errores en el formulario.")
        return super().form_invalid(form)