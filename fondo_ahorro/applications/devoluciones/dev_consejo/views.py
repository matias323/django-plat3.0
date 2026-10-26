from django.shortcuts import render

# Create your views here.
# Create your views here.
from django.views.generic import TemplateView

from django.contrib.auth.mixins import LoginRequiredMixin

class ConsejoView(LoginRequiredMixin,TemplateView):
    template_name = 'devolucion/consejo/consejo.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # context['usuarios'] = User.objects.filter(id=self.request.user.id)

        # if self.request.user.is_authenticated:
        #     session = Session.objects.filter(user__id=self.request.user.id,closed_at = None) or None #arreglar esto 

        #     if session:
        #         apps = App.objects.filter(
        #                             userpermission__is_active=True,
        #                             father_app__isnull=True, #solo los padres
        #                             roleapp__role = session[0].role, 
        #                             roleapp__role__roleuser__user= session[0].user,
        #                             roleapp__is_active = True,
        #                             )
        #         context['apps'] =apps
        
        
        return context
