from dataclasses import dataclass, field
from django.db import transaction

from .models import Cuentas


@dataclass
class CuentaNodo:
    cuenta: Cuentas
    subcuentas: list = field(default_factory=list)
    

# obtiene plan de cuentas completo
def obtener_plan_cuentas():
    cuentas = list(Cuentas.objects.select_related("cuenta_tipo", "cuenta_padre").order_by("num_cuenta"))
    
    nodos = {
        cuenta.id: CuentaNodo(cuenta=cuenta)
        for cuenta in cuentas
    }
    
    arbol = []
    
    for cuenta in cuentas:
        nodo = nodos[cuenta.id]
        
        if cuenta.cuenta_padre_id is None:
            arbol.append(nodo)
        else:
            padre = nodos.get(cuenta.cuenta_padre_id)
            
            if padre:
                padre.subcuentas.append(nodo)
    
    return arbol

# realiza la activacion de una cuenta contable y las cuentas padres si corresponde
@transaction.atomic
def activar_cuenta(cuenta_id):
    try:
        cuenta = Cuentas.objects.select_related("cuenta_padre").get(pk=cuenta_id)
        
    except Cuentas.DoesNotExist:
        raise ValueError("Cuenta no encontrada")
    
    if cuenta.is_activate:
        raise ValueError("La cuenta ya esta activada")
    
    cuentas_activadas = []
    
    cuenta_actual = cuenta
    
    while cuenta_actual is not None:
        cuenta_actual.is_active = True
        
        cuenta_actual.save(update_fields=["is_activate"])
        
        cuentas_activadas.appernd(cuenta_actual)
        
        cuenta_actual = cuenta_actual.cuenta_padre
    
    return cuentas_activadas
            



