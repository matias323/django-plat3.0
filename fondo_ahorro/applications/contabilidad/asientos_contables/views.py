from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from http import HTTPStatus
from django.contrib.auth.mixins import LoginRequiredMixin
from .services import AsientoContableServices
import json
from .models.asientos_contables import AsientoContableTipo
from applications.contabilidad.plan_cuentas.models import Cuentas
from applications.contabilidad.periodo_contable.services import PeriodoContableServices
from .utils import get_month_name

# Create your views here.
from django.views.generic import TemplateView

class AsientosContablesView(TemplateView):
    template_name = 'contabilidad/asientos_contables/ingreso_asiento_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context["tipos_asientos"] = AsientoContableTipo.ingreso_manual()
        
        periodo = PeriodoContableServices.get_periodo_contable_actual()
        
        anio = periodo.year
        mes = get_month_name(periodo.month)
        
        context["catalogo_cuentas"] = Cuentas.get_catalogo_cuentas()
        
        context["periodo"] = f"{mes}-{anio}"
        context["cuentas"] = Cuentas.get_cuentas_hijas()
        
        return context

    
class AsientoContableEncabezadoView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            #validar usuario
            user = request.user
            
            #post
            entry_date = request.POST.get("entry_date")
            description = request.POST.get("description")
            entry_type = request.POST.get("entry_type")
            
            #validacion
            if not entry_date:
                return JsonResponse({"success":False, "message":"La fecha del asiento es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
            if not entry_type:
                return JsonResponse({"success":False, "message":"El tipo de asiento es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            #crear asiento
            asiento = AsientoContableServices.crear_encabezado_asiento(user, entry_date, description, entry_type)
            
            return JsonResponse({
                "success":True, 
                "message":"Asiento creado correctamente", 
                "data":asiento.asiento_to_dict()}, status=HTTPStatus.OK)
        
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            
    

class AsientoMovimientoCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            user = request.user
            
            account = request.POST.get("account")
            description = request.POST.get("description")
            debit = request.POST.get("debit", 0)
            credit = request.POST.get("credit", 0)
            
            #validar debe y haber
            try:
                debit = int(debit or 0)
                credit = int(credit or 0)
            except (TypeError, ValueError):
                JsonResponse({"success":False, "message":"Debe y haber deben ser validos"}, status=HTTPStatus.BAD_REQUEST)    
            
            #auxiliares
            auxiliares = []
            if request.POST.get("auxiliares"):
                try:
                    auxiliares = json.loads(request.POST.get("auxiliares"))
                except json.JSONDecodeError:
                    return JsonResponse({"success":False, "message":"Los auxiliares deben ser validos"}, status=HTTPStatus.BAD_REQUEST)
            
            #crear movimeinto
            movimiento = AsientoContableServices.crear_movimiento(user, pk, account, debit, credit, description, auxiliares)
            
            return JsonResponse({
                "success": True,
                "message": "Movimiento creado correctamente",
                "data": movimiento.movimiento_to_dict()
            }, status=HTTPStatus.OK)
        
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            
class AsientoPersonaSearchView(View):
    def get(self, request):
        try:
            search = request.GET.get("q","")
            
            data = AsientoContableServices.search_persons(search)
            
            return JsonResponse({"success":True, "data":data}, status=HTTPStatus.OK)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)