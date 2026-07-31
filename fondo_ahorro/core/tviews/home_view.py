from django.views.generic import TemplateView

from core.models.user import User

from applications.role.models import RoleApp
from applications.apps.models import App

from core.models.session import Session

class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['usuarios'] = User.objects.filter(id=self.request.user.id)

        if self.request.user.is_authenticated:
            session = Session.objects.filter(user__id=self.request.user.id,closed_at = None).first() or None #arreglar esto 
            if session:
                context['session'] = session
        
        
        return context
