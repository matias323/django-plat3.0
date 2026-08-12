from dataclasses import dataclass, field

from .models import Cuentas


@dataclass
class CuentaNodo:
    cuenta: Cuentas
    subcuentas: list = field(default_factory=list)
    

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





