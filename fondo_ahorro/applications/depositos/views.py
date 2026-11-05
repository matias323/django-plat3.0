from django.shortcuts import render
from django.views import View
from django.http import JsonResponse, HttpResponse
from http import HTTPStatus
from .service import DepositoServices
from .service_report import ReportService
from datetime import datetime
import json
from core.models.partner import PartnerContributionType, PartnerMovement, PartnerMovementType
from django.db.models.functions import ExtractYear

from .models import ProcessType

# Create your views here. 
from django.views.generic import TemplateView



def obtener_client_ip(request):
    # 1. Intentar obtener la IP desde el encabezado X-Forwarded-For (común si usas Nginx, proxies o Cloudflare)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    
    if x_forwarded_for:
        # X-Forwarded-For puede contener una lista de IPs separadas por comas; la primera es el cliente real
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        # 2. Si no hay proxy, obtener la dirección IP remota directa de la conexión
        ip = request.META.get('REMOTE_ADDR')
        
    return ip

# vista creacion incremento de aportes
class DepositoView(TemplateView):
    template_name = 'depositos/incrementos/incremento_aporte_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        return context
    
# vista busqueda de depositos
class DepositoSearchView(TemplateView):
    template_name = 'depositos/busqueda/busqueda_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context["tipo_proceso"] = ProcessType.objects.all()
        
        return context
    
# vista cartola movimientos
class DepositoCartola(TemplateView):
    template_name = 'depositos/cartola/cartola_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # context["movements_years"] = list(PartnerMovement.objects.dates("created_at", "year", order="DESC").values_list("created_at__year", flat=True).distinct())
        context["movements_years"] = list(PartnerMovement.objects.annotate(year=ExtractYear("created_at")).values_list("year", flat=True).distinct().order_by("-year"))
        
        context["movements_types"] = list(PartnerMovementType.objects.all())
        
        context["contribution_types"] = list(PartnerContributionType.objects.all())
        
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
        
#incremento de aportes
class DepositoIncrementoAporte(View):
    def post(self, request):
        try:
            #post
            monto = int(request.POST.get("monto"))
            num_deposito = int(request.POST.get("numero_operacion"))
            fecha_deposito = request.POST.get("fecha_operacion")
            aporte_tipo = int(request.POST.get("cuenta"))
            persona_id = int(request.POST.get("persona"))
            socio_id = int(request.POST.get("socio"))
            
            #validar usuario
            user = request.user
            
            #adjuntos
            archivos_adjuntos = request.FILES.getlist("adjuntos")
            
            #validar
            if not monto or monto < 1:
                return JsonResponse({"success":False, "message":"El monto es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            if not num_deposito or num_deposito < 1:
                return JsonResponse({"success":False, "message":"El número de operación es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            if not fecha_deposito:
                return JsonResponse({"success":False, "message":"La fecha de operación es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
            try:
                # 2. Validar que el formato de la fecha sea correcto
                fecha_valida = datetime.strptime(fecha_deposito, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({"success": False, "message": "Formato de fecha inválido (use YYYY-MM-DD)"}, status=HTTPStatus.BAD_REQUEST)
            
            if not aporte_tipo or aporte_tipo < 1:
                return JsonResponse({"success":False, "message":"El tipo de aporte es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            if not persona_id or persona_id < 1:
                return JsonResponse({"success":False, "message":"La persona es requerida"}, status=HTTPStatus.BAD_REQUEST)
            
            if not socio_id or socio_id < 1:
                return JsonResponse({"success":False, "message":"El socio es requerido"}, status=HTTPStatus.BAD_REQUEST)
            
            #validar adjuntos
            if not archivos_adjuntos:
                return JsonResponse({"success":False, "message":"Los archivos adjuntos son requeridos"}, status=HTTPStatus.BAD_REQUEST)
            
            # 3. Validar que todos los archivos sean estrictamente PDF
            for archivo in archivos_adjuntos:
                # Verificamos la extensión del nombre del archivo (en minúsculas)
                nombre_valido = archivo.name.lower().endswith('.pdf')
                
                # Verificamos opcionalmente el tipo MIME que reporta el navegador/cliente
                mime_valido = archivo.content_type == 'application/spec_or_pdf' or archivo.content_type == 'application/pdf'
                
                if not nombre_valido or not mime_valido:
                    return JsonResponse(
                        {
                            "success": False, 
                            "message": f"El archivo '{archivo.name}' no es un PDF válido. Solo se permiten archivos en formato PDF."
                        },
                        status=HTTPStatus.BAD_REQUEST
                    )
            
            #obtener ip
            ip = obtener_client_ip(request)
            
            #guardar
            deposito = DepositoServices.registrar_incremento_aporte(monto, num_deposito, fecha_valida, aporte_tipo, persona_id, socio_id, archivos_adjuntos, user, ip)

            return JsonResponse({"success":True, "message":"Operación realizada con éxito", "data":deposito.id}, status=HTTPStatus.OK)
            
        except ValueError as e:
                    return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.BAD_REQUEST)
                
        except Exception as e:
            return JsonResponse({"success":False, "message":str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
  
  
#busqueda de depositos
class DepositosBusqueda(View):
    def post(self, request): 
        #post
        data = json.loads(request.body)   
        query = data.get("query", None)
        tipoProceso = data.get("tipo")
        fechaDesde = data.get("fechaDesde")
        fechaHasta = data.get("fechaHasta")
        montoMin = data.get("montoMin")
        montoMax = data.get("montoMax")
        
        
        tipoProceso = tipoProceso if int(tipoProceso) > 0 else None
        montoMin = montoMin if int(montoMin) > 0 else None
        montoMax = montoMax if int(montoMax) > 0 else None
        fechaDesde = datetime.strptime(fechaDesde, "%Y-%m-%d") if fechaDesde else None
        fechaHasta = datetime.strptime(fechaHasta, "%Y-%m-%d") if fechaHasta else None
        
        depositos = DepositoServices.search_deposito(None, None, query, tipoProceso, fechaDesde, fechaHasta, montoMin, montoMax)
        return JsonResponse({"success":True, "data":depositos}, status=HTTPStatus.OK)
        
        
        
        
        
        
        
           

#generar pdf
class DepositoIncrementoAportePDF(View):
    def get(self, request, pk):
        try:
            pk = int(pk)
            
            #validar pk
            if pk <= 0:
                return HttpResponse("No es posible generar el asiento", status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user
            
            data = DepositoServices.search_deposito(pk)
            
            if not data:
                return HttpResponse("No es posible generar el asiento", status=HTTPStatus.BAD_REQUEST)
            
            pdf = ReportService.comprobante_pdf(data, user)
                                    
            response = HttpResponse(pdf, content_type='application/pdf')
            
            response['Content-Disposition'] = f'attachment; filename="comprobante_incremento_{data[0]["deposit_number"]}.pdf"'
            
            return response
        
        except ValueError as e:
            return HttpResponse(str(e), status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return HttpResponse(str(e), status=HTTPStatus.INTERNAL_SERVER_ERROR)
        

#generar comprobante
class DepositoAppComprobantePDF(View):
    def get(self, request, pk):
        try:
            pk = int(pk)
            # print()
            #validar pk
            if pk <= 0:
                return HttpResponse("No es posible generar el asiento", status=HTTPStatus.BAD_REQUEST)
            
            #validar usuario
            user = request.user
            
            data = DepositoServices.search_deposito(None, None, None, None, None, None, None, None, None, pk)
            # print(data)
            
            if not data:
                return HttpResponse("No es posible generar el asiento", status=HTTPStatus.BAD_REQUEST)
            
            pdf = ReportService.comprobante_pdf(data, user)
                                    
            response = HttpResponse(pdf, content_type='application/pdf')
            
            response['Content-Disposition'] = f'attachment; filename="comprobante.pdf"'
            
            return response
        
        except ValueError as e:
            return HttpResponse(str(e), status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return HttpResponse(str(e), status=HTTPStatus.INTERNAL_SERVER_ERROR)
        
#cartola movimeiento
class CartolaMovimientos(View):
    def post(self, request):
        data = json.loads(request.body)
                
        anio = int(data.get("anio", 0))
        tipo = int(data.get("tipo", 0))
        cuenta = int(data.get("cuenta", 0))
        persona = int(data.get("persona", 0))
        
        anio = int(anio) if anio > 0 else None
        tipo = int(tipo) if tipo > 0 else None
        cuenta = int(cuenta) if cuenta > 0 else None
        persona = int(persona) if persona > 0 else None
        
        if persona == None:
            return JsonResponse({"success":False, "message":"No se ha seleccionado una persona"}, status=HTTPStatus.BAD_REQUEST)
        
        movimientos = DepositoServices.search_movimientos(anio, tipo, cuenta, persona)
        saldos = DepositoServices.saldo_anio(persona, anio, cuenta, tipo)
        return JsonResponse({"success":True, "data":movimientos, "saldo":saldos}, status=HTTPStatus.OK)
        