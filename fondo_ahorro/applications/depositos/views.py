from django.shortcuts import render
from django.views import View
from django.http import JsonResponse, HttpResponse
from http import HTTPStatus
from .service import DepositoServices

# Create your views here. 
from django.views.generic import TemplateView

# vista creacion incremento de aportes
class DepositoView(TemplateView):
    template_name = 'depositos/incrementos/incremento_aporte_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # context["tipos_asientos"] = AsientoContableTipo.ingreso_manual()
        
        # periodo = PeriodoContableServices.get_periodo_contable_actual()
        # anio = periodo.year
        # mes = get_month_name(periodo.month)
        
        # context["catalogo_cuentas"] = Cuentas.get_catalogo_cuentas()
        
        # context["periodo"] = f"{mes}-{anio}"
        # context["cuentas"] = Cuentas.get_cuentas_hijas()
        
        return context
    
#busqueda de personas
class DepositoPartnerSearch(View):
    def get(self, request):
        try:
            search = request.GET.get("q","")
            
            data = DepositoServices.search_persons(search)
            
            return JsonResponse({"success":True, "data":data}, status=HTTPStatus.OK)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)