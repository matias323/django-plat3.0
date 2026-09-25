from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from http import HTTPStatus
from django.contrib.auth.mixins import LoginRequiredMixin
from .services import AsientoContableServices
from .services_pdf import AsientoContableServicePDF, LibroDiarioPDF
import json
from .models.asientos_contables import AsientoContableTipo, AsientoContableEstado
from applications.contabilidad.plan_cuentas.models import Cuentas
from applications.contabilidad.periodo_contable.services import PeriodoContableServices
from .utils import get_month_name
from datetime import datetime


# Create your views here.
from django.views.generic import TemplateView

# vista creacion de asiento contable
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
    
# vista asientos periodo
class AsientosContablesPeriodoView(TemplateView):
    template_name = 'contabilidad/asientos_periodo/asiento_periodo_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        periodo = PeriodoContableServices.get_periodo_contable_actual()
        anio = periodo.year
        mes = get_month_name(periodo.month)
        context["periodo"] = f"{mes}-{anio}"
        
        context["catalogo_cuentas"] = Cuentas.get_catalogo_cuentas()
        
        return context 
    
# vista busqueda de asientos
class AsientosContablesBusquedaView(TemplateView):
    template_name = 'contabilidad/asientos_busqueda/busqueda_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        periodos = PeriodoContableServices.get_periodos_contables()
        context["periodos"] = periodos
        context["asientos_tipos"] = AsientoContableTipo.todos()
        context["asientos_estados"] = AsientoContableEstado.estados()

        return context 
    
# vista libro diario
class LibroDiarioView(TemplateView):
    template_name = 'contabilidad/libro_diario/libro_diario_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        periodos = PeriodoContableServices.get_periodos_contables()
        context["periodos"] = periodos
        context["asientos_tipos"] = AsientoContableTipo.todos()
        context["asientos_estados"] = AsientoContableEstado.estados()
        
        return context
        

class AsientoContableCreate(LoginRequiredMixin, View):
    def post(self, request):
        try:
            
            #validar usuario
            user = request.user
            
            #post
            data = json.loads(request.body)
            
            entry_date = data.get("fechaAsiento")
            description = data.get("glosaGeneral")
            entry_type = data.get("tipoAsiento")
            movements = data.get("movimientos", [])
            totalDebit = data.get("totalDebe", 0)
            totalCredit = data.get("totalHaber", 0)
            
            #validacion
            if not entry_date:
                return JsonResponse({"success":False, "message":"La fecha del asiento es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
            if not description:
                return JsonResponse({"success":False, "message":"La glosa general es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
            if not entry_type:
                return JsonResponse({"success":False, "message":"El tipo de asiento es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            if totalDebit != totalCredit or totalDebit == 0 or totalCredit == 0:
                return JsonResponse({"success":False, "message":"El total debe y haber deben ser iguales"}, status=HTTPStatus.BAD_REQUEST)
            
            if not movements:
                return JsonResponse({"success":False, "message":"El movimiento del asiento es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            #asiento manual no debe utilizar cuenta banco(11102, id=13)
            existe = any(movement.get("account") == 13 for movement in movements) 
            if existe:
                return JsonResponse({"success":False, "message":"El asiento manual no debe utilizar la cuenta de banco"}, status=HTTPStatus.BAD_REQUEST)   
                
            #crear asiento
            asiento = AsientoContableServices.crear_asiento_completo(user, entry_date, description, entry_type, movements)
            return JsonResponse({
                "success":True, 
                "message":"Asiento creado correctamente", 
                "data":asiento.asiento_to_dict()}, status=HTTPStatus.OK)
        
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
 
            
#busqueda de personas
class AsientoPersonaSearchView(View):
    def get(self, request):
        try:
            search = request.GET.get("q","")
            
            data = AsientoContableServices.search_persons(search)
            
            return JsonResponse({"success":True, "data":data}, status=HTTPStatus.OK)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
           
 
 # obtiene los asientos del periodo activo
class AsientosContablesPeriodoAllView(View):
    def get(self, request):
        try:
            data = AsientoContableServices.asientos_periodo_activo()
            return JsonResponse({"success":True, "data":data}, status=HTTPStatus.OK)
        
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
#verificar si se puede editar el asiento y bloquear asiento
class AsientoContableCheckView(View):
    def post(self, request):
        try:
            pk = request.POST.get("idAsiento")
            version = request.POST.get("version")
            pk = int(pk)
            version = int(version)
            
            #validar pk y version
            if pk <= 0 or version <= 0:
                return JsonResponse({"success":False, "message":"No es posible editar el asiento"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user
            
            data = AsientoContableServices.check_asiento_edit(pk, version, user)
            return JsonResponse(data, status=HTTPStatus.OK)
        
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
    #quitar bloqueo
    def get(self, request, pk):
        try:
            pk = int(pk)
                        
            #validar pk
            if pk <= 0:
                return JsonResponse({"success":False, "message":"No es posible quitar el bloqueo al asiento"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user
            
            AsientoContableServices.uncheck_asiento(user, pk)
            return JsonResponse({"success":True, "message":"Asiento desbloqueado correctamente"}, status=HTTPStatus.OK)
            
            
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)   

     

# editar asiento
class AsientoContableUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            pk = int(pk)
            
            #validar pk
            if pk <= 0:
                return JsonResponse({"success":False, "message":"No es posible editar el asiento"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user
            
            #post
            data = json.loads(request.body)
            
            description = data.get("glosaGeneral")
            movements = data.get("movimientos", [])
            totalDebit = data.get("totalDebe", 0)
            totalCredit = data.get("totalHaber", 0)
                        
            #validacion 
            if not description:
                return JsonResponse({"success":False, "message":"La glosa general es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
            if totalDebit != totalCredit or totalDebit == 0 or totalCredit == 0:
                return JsonResponse({"success":False, "message":"El total debe y haber deben ser iguales"}, status=HTTPStatus.BAD_REQUEST)
            
            if not movements:
                return JsonResponse({"success":False, "message":"El movimiento del asiento es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            #asiento manual no debe utilizar cuenta banco(11102, id=13)
            existe = any(movement.get("account") == 13 for movement in movements) 
            if existe:
                return JsonResponse({"success":False, "message":"El asiento manual no debe utilizar la cuenta de banco"}, status=HTTPStatus.BAD_REQUEST)  
            
            #editar asiento
            asiento = AsientoContableServices.editar_asiento(user, pk, description, movements)
            return JsonResponse({
                "success":True, 
                "message":"Asiento modificado correctamente", 
                "data":asiento.asiento_to_dict()}, status=HTTPStatus.OK)
                    
            
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
        
# anular asiento
class AsientoContableAnularView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            pk = int(pk)
                        
            #validar pk
            if pk <= 0:
                return JsonResponse({"success":False, "message":"No es posible anular el asiento"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user 
            
            AsientoContableServices.anular_asiento(user, pk)
            return JsonResponse({"success":True, "message":"Asiento anulado correctamente"}, status=HTTPStatus.OK)
            
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        


# quitar nulo asiento
class AsientoContableQuitarNuloView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            pk = int(pk)
                        
            #validar pk
            if pk <= 0:
                return JsonResponse({"success":False, "message":"No es posible activar el asiento"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user 
            
            AsientoContableServices.quitar_nulo_asiento(user, pk)
            return JsonResponse({"success":True, "message":"Asiento activado correctamente"}, status=HTTPStatus.OK)
            
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
#validar asiento
class AsientoContableValidateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            pk = int(pk)
                                    
            #validar pk
            if pk <= 0:
                return JsonResponse({"success":False, "message":"No es posible activar el asiento"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user 
            
            AsientoContableServices.contabilizar_asiento(user, pk)
            return JsonResponse({"success":True, "message":"Asiento contabilizado correctamente"}, status=HTTPStatus.OK)
            
        except ValueError as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
#busqueda de asientos contables
class AsientosContablesBuscarView(LoginRequiredMixin, View):
    def post(self, request):
        #post
        data = json.loads(request.body)
        
        numero = int(data.get("num", 0))
        periodo = int(data.get("periodo"))
        tipo = int(data.get("tipo"))
        estado = int(data.get("estado"))
        fechaDesde = data.get("fechaDesde")
        fechaHasta = data.get("fechaHasta")
        
        numero = int(numero) if numero > 0 else None
        periodo = int(periodo) if periodo > 0 else None
        tipo = int(tipo) if tipo > 0 else None
        estado = int(estado) if estado > 0 else None
        fechaDesde = datetime.strptime(fechaDesde, "%Y-%m-%d") if fechaDesde else None
        fechaHasta = datetime.strptime(fechaHasta, "%Y-%m-%d") if fechaHasta else None
        
        asientos = AsientoContableServices.buscar_asientos(numero, periodo, tipo, estado, fechaDesde, fechaHasta)
        return JsonResponse({"success":True, "data":asientos}, status=HTTPStatus.OK)
        
        
        
#generar PDF ASIENTO CONTABLE
class AsientoContablePDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            pk = int(pk)
            
            #validar pk
            if pk <= 0:
                return HttpResponse("No es posible generar el asiento", status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user
            
            data = AsientoContableServices.asiento_pdf(pk)
            
            if not data:
                return HttpResponse("No es posible generar el asiento", status=HTTPStatus.BAD_REQUEST)
            
            pdf = AsientoContableServicePDF.generate_asiento_pdf(data, user)
            
            response = HttpResponse(pdf, content_type='application/pdf')
            
            response['Content-Disposition'] = f'attachment; filename="asiento_contable_{data["numero_comprobante"]}.pdf"'
            
            return response
        
        except ValueError as e:
            return HttpResponse(str(e), status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return HttpResponse(str(e), status=HTTPStatus.INTERNAL_SERVER_ERROR)
    
class LibroDiarioPDFView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            #post
            data = json.loads(request.body)
            
            periodo = int(data.get("periodo"))
            tipo = int(data.get("tipo"))
            estado = int(data.get("estado"))
            fechaDesde = data.get("fechaDesde")
            fechaHasta = data.get("fechaHasta")
            
            #validar usuario
            user = request.user

            periodo = int(periodo) if periodo > 0 else None
            tipo = int(tipo) if tipo > 0 else None
            estado = int(estado) if estado > 0 else None
            fechaDesde = datetime.strptime(fechaDesde, "%Y-%m-%d") if fechaDesde else None
            fechaHasta = datetime.strptime(fechaHasta, "%Y-%m-%d") if fechaHasta else None
            
            data = AsientoContableServices.buscar_asientos(None, periodo, tipo, estado, fechaDesde, fechaHasta)
            
            if not data:
                return HttpResponse("No es posible generar el Libro diario", status=HTTPStatus.BAD_REQUEST)
            
            pdf = LibroDiarioPDF.generate_libro_diario_pdf(data, user)
            
            response = HttpResponse(pdf, content_type='application/pdf')
            
            response['Content-Disposition'] = f'attachment; filename="libro_diario.pdf"'
            
            return response
        
        except ValueError as e:
            return HttpResponse(str(e), status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return HttpResponse(str(e), status=HTTPStatus.INTERNAL_SERVER_ERROR)
        




# class AsientoContableEncabezadoView(LoginRequiredMixin, View):
#     def post(self, request):
#         try:
#             #validar usuario
#             user = request.user
            
#             #post
#             entry_date = request.POST.get("entry_date")
#             description = request.POST.get("description")
#             entry_type = request.POST.get("entry_type")
            
#             #validacion
#             if not entry_date:
#                 return JsonResponse({"success":False, "message":"La fecha del asiento es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
#             if not entry_type:
#                 return JsonResponse({"success":False, "message":"El tipo de asiento es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
#             #crear asiento
#             asiento = AsientoContableServices.crear_encabezado_asiento(user, entry_date, description, entry_type)
            
#             return JsonResponse({
#                 "success":True, 
#                 "message":"Asiento creado correctamente", 
#                 "data":asiento.asiento_to_dict()}, status=HTTPStatus.OK)
        
#         except ValueError as e:
#             return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        
#         except Exception as e:
#             return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            
    

# class AsientoMovimientoCreateView(LoginRequiredMixin, View):
#     def post(self, request, pk):
#         try:
#             user = request.user
            
#             account = request.POST.get("account")
#             description = request.POST.get("description")
#             debit = request.POST.get("debit", 0)
#             credit = request.POST.get("credit", 0)
            
#             #validar debe y haber
#             try:
#                 debit = int(debit or 0)
#                 credit = int(credit or 0)
#             except (TypeError, ValueError):
#                 JsonResponse({"success":False, "message":"Debe y haber deben ser validos"}, status=HTTPStatus.BAD_REQUEST)    
            
#             #auxiliares
#             auxiliares = []
#             if request.POST.get("auxiliares"):
#                 try:
#                     auxiliares = json.loads(request.POST.get("auxiliares"))
#                 except json.JSONDecodeError:
#                     return JsonResponse({"success":False, "message":"Los auxiliares deben ser validos"}, status=HTTPStatus.BAD_REQUEST)
            
#             #crear movimeinto
#             movimiento = AsientoContableServices.crear_movimiento(user, pk, account, debit, credit, description, auxiliares)
            
#             return JsonResponse({
#                 "success": True,
#                 "message": "Movimiento creado correctamente",
#                 "data": movimiento.movimiento_to_dict()
#             }, status=HTTPStatus.OK)
        
#         except ValueError as e:
#             return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
        
#         except Exception as e:
#             return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR) 