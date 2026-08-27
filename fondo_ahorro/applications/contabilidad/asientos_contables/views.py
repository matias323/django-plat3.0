from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from http import HTTPStatus

# Create your views here.
from django.views.generic import TemplateView

class AsientosContablesView(TemplateView):
    template_name = 'contabilidad/asientos_contables/crear_asiento.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # context['arbol'] = obtener_plan_cuentas()
        
        return context