from django.contrib import admin

# Register your models here.
from .models import (
    AsientoContable, 
    AsientoContableCorrelativo, 
    AsientoContableTipo, 
    AsientoContableEstado, 
    AsientoMovimiento, 
    AsientoMovimientoAux,
    AsientoContableAprobacion)

# Register your models here.
admin.site.register(AsientoContable)
admin.site.register(AsientoContableCorrelativo)
admin.site.register(AsientoContableTipo)
admin.site.register(AsientoContableEstado)
admin.site.register(AsientoMovimiento)
admin.site.register(AsientoMovimientoAux)
admin.site.register(AsientoContableAprobacion)