from django.contrib import admin

# Register your models here.
from .models import Cuentas, CuentasType

admin.site.register(Cuentas)
admin.site.register(CuentasType)

