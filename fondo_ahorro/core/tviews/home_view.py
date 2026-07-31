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
            session = Session.objects.filter(user__id=self.request.user.id,closed_at = None) or None

            if session:
                apps = App.objects.filter(
                                    father_app__isnull=True,
                                    roleapp__role = session[0].role,
                                    roleapp__role__roleuser__user= session[0].user 
                                    )
                context['apps'] =apps
        
        
        return context
