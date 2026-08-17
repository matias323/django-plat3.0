from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from http import HTTPStatus

from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from .models import Cuentas

# Create your views here.
from django.views.generic import TemplateView

from .services import obtener_plan_cuentas, activar_cuenta

class CuentaView(TemplateView):
    template_name = 'contabilidad/plan_cuentas/plan_cuenta.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['arbol'] = obtener_plan_cuentas()
        
        return context
    
    
    

# editar cuenta activa
@method_decorator(require_POST, name='dispatch')
class EditarCuentaApiView(View):
    
    def post(self, request, pk):
        try:
            cuenta = Cuentas.objects.get(pk=pk, is_active=True)
        except Cuentas.DoesNotExist:
            return JsonResponse({"success":False, 'message': 'Cuenta no encontrada'}, status=HTTPStatus.NOT_FOUND)

        # validaciones
        if request.POST.get('nombre')==None:
            return JsonResponse({"success":"error", "message":"El campo nombre es obligatorio"}, status=HTTPStatus.BAD_REQUEST)
        
        if len(request.POST.get('nombre'))<5:
            return JsonResponse({"success":"error", "message":"El nombre debe tener al menos 5 caracteres"}, status=HTTPStatus.BAD_REQUEST)
        
        if request.POST.get('descripcion') == None:
            return JsonResponse({"success":"error", "message":"El campo descripcion es obligatorio"}, status=HTTPStatus.BAD_REQUEST)
        
        if request.POST.get('is_auxiliar') == None:
            return JsonResponse({"success":"error", "message":"El campo is_auxiliar es obligatorio"}, status=HTTPStatus.BAD_REQUEST)
        
        if request.POST.get('tratamiento_especial') == None:
            return JsonResponse({"success":False, "message":"El campo tratamiento_especial es obligatorio"}, status=HTTPStatus.BAD_REQUEST)
        
        nombre = request.POST.get('nombre').strip()
        descripcion = request.POST.get('descripcion') or ""
        is_auxiliar = request.POST.get('is_auxiliar') == 'true'
        tratamiento_especial = request.POST.get('tratamiento_especial') == 'true'
        
        #actualizar
        cuenta.nombre = nombre.upper()
        cuenta.descripcion = descripcion.upper()
        cuenta.is_auxiliar = is_auxiliar
        cuenta.tratamiento_especial = tratamiento_especial
        
        #solo permite actualizar los campos de nombre, descripcion, is_auxiliar y tratamiento_especial
        cuenta.save(
            update_fields=[
                'nombre',
                'descripcion',
                'is_auxiliar',
                'tratamiento_especial'
            ]
        )

        return JsonResponse(
            {
                "success":True, 
                "message":"Cuenta editada correctamente", 
                "cuenta":cuenta.cuenta_to_dict()
            }, status=HTTPStatus.OK)


class ExportarPlanCuentasView(View):
    
    def get(self, request):
        cuentas = Cuentas.objects.filter(is_active=True).select_related("cuenta_tipo", "cuenta_padre").order_by('num_cuenta')
        
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Plan de Cuentas"
        
        #titulo
        sheet["A1"] = "PLAN DE CUENTAS"
        sheet["A1"].font = Font(bold=True, size=16)
        
        sheet.merge_cells("A1:H1")
        sheet["A1"].alignment = Alignment(horizontal="center")
        
        #encabezado
        headers = [
            "N° Cuenta",
            "Nombre",
            "Descripcion",
            "Nivel",
            "Cuenta Padre",
            "Tipo de Cuenta",
            "Auxiliar",
            "Tratamiento Especial"
        ]
        
        for columna, header in enumerate(headers, start=1):
            celda = sheet.cell(row=3, column=columna)
            
            celda.value = header
            celda.font = Font(bold=True)
            celda.alignment = Alignment(horizontal="center", vertical="center")
            
        #datos
        fila = 4
        
        for cuenta in cuentas:
            sheet.cell(row=fila, column=1, value=cuenta.num_cuenta)
            sheet.cell(row=fila, column=2, value=cuenta.nombre)
            sheet.cell(row=fila, column=3, value=cuenta.descripcion or "")
            sheet.cell(row=fila, column=4, value=cuenta.nivel)
            sheet.cell(row=fila, column=5, value=(cuenta.cuenta_padre.num_cuenta if cuenta.cuenta_padre else ""))
            sheet.cell(row=fila, column=6, value=cuenta.cuenta_tipo.descripcion)
            sheet.cell(row=fila, column=7, value="Si" if cuenta.is_auxiliar else "No")
            sheet.cell(row=fila, column=8, value="Si" if cuenta.tratamiento_especial else "No")
            
            fila += 1
        
        anchos = {
            "A": 15,
            "B": 120,
            "C": 30,
            "D": 10,
            "E": 15,
            "F": 20,
            "G": 15,
            "H": 20
        }
        
        for columna, ancho in anchos.items():
            sheet.column_dimensions[columna].width = ancho
        
        sheet.freeze_panes = "A4"
        
        output = BytesIO()
        workbook.save(output)
        
        output.seek(0)
        
        response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        response["Content-Disposition"] = ('attachment; filename="plan_cuentas.xlsx"')
        
        return response
        
#activacion de cuentas
@method_decorator(require_POST, name='dispatch')
class ActivarCuentaView(View):
    def post(self, request, cuenta_id): 
        try:
            cuentas_activadas = activar_cuenta(cuenta_id)
        except ValueError as e:
            return JsonResponse(
                {
                    "success":False, 
                    "message":str(e) or "Ocurrio un error inesperado al activar la cuenta"
                }, status=HTTPStatus.BAD_REQUEST)
        
        return JsonResponse(
            {
                "success":True, 
                "message":"Cuentas activadas correctamente", 
                "cuentas_activadas":[cuenta.cuenta_to_dict() for cuenta in cuentas_activadas]
            }, status=HTTPStatus.OK)
        
        