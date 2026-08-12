from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from http import HTTPStatus

from .models import Cuentas

# Create your views here.
from django.views.generic import TemplateView

from .services import obtener_plan_cuentas

class CuentaView(TemplateView):
    template_name = 'contabilidad/plan_cuentas/plan_cuenta.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['arbol'] = obtener_plan_cuentas()
        
        return context
    
    
    

# editar cuenta activa
# @method_decorator(require_POST, name='dispatch')
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
        cuenta.nombre = nombre
        cuenta.descripcion = descripcion
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


