from django.shortcuts import render
from django.views import View

# Create your views here.
from django.views.generic import TemplateView

# Create your views here.
class PeriodoContableView(TemplateView):
    template_name = 'contabilidad/periodo_contable/periodo_contable.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # context['arbol'] = obtener_plan_cuentas()
        
        return context
  