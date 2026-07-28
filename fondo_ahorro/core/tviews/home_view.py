from django.views.generic import TemplateView

from core.models.user import User, UserType

class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['usuarios'] = User.objects.filter()
        
        return context
