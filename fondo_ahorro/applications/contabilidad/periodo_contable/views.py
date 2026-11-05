from django.shortcuts import render
from django.views import View
from .models import PeriodoContable
from .services import PeriodoContableServices, get_month_name

# Create your views here.
from django.views.generic import TemplateView
from django.http import JsonResponse
from http import HTTPStatus

# Create your views here.
class PeriodoContableTemplate(TemplateView):
    template_name = 'contabilidad/periodo_contable/periodo_contable.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        return context
    
# registros periodos datatable
class PeriodoContableView(View):
    
    #listar todos los periodos
    def get(self, request):
        data = PeriodoContableServices.get_periodos_contables()
        return JsonResponse({"success": True, "data": data}, status=HTTPStatus.OK)
    
    #abrir nuevo periodo
    def post (self, request):
        try:
            user = request.user
            nuevo_periodo = PeriodoContableServices.crear_nuevo_periodo(user)
            
            return JsonResponse(
                {
                    "success": True, 
                    "message": "Periodo creado correctamente", 
                    "data": nuevo_periodo.periodo_to_dict()
                }, status=HTTPStatus.CREATED)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=HTTPStatus.BAD_REQUEST)

        
  