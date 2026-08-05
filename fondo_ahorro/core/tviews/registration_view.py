from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from core.models.person import Person
from core.forms.person_form import PersonForm

class RegistrationView(CreateView):
    model = Person
    form_class = PersonForm
    template_name = 'registration/registration.html'
    success_url = reverse_lazy('registro_exitoso')  # Redirige a una página de confirmación pública

    def form_valid(self, form):
        persona = form.save(commit=False)
        
        # Al ser un registro público:
        # 1. Si user_create_id acepta NULL en tu modelo:
        persona.user_create_id = None
        
        # 2. O si obligatoriamente requiere un ID, asignas un usuario del sistema (ej: ID 1):
        # persona.user_create_id = 1
        
        persona.save()
        
        messages.success(self.request, "Tu registro se ha completado con éxito.")
        return super().form_valid(form)