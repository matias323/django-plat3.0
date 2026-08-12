from django.db import models

from core.models.base import BaseModel

# Create your models here.
class CuentasType(BaseModel):
    descripcion = models.CharField(max_length=100, verbose_name="Descripcion", null=False, blank=False)
    
    def __str__(self):
        return self.descripcion
    
    class Meta:
        db_table = "contab_cuenta_tipo"
        verbose_name = "Tipo de Cuenta"
        verbose_name_plural = "Tipos de Cuentas"
        
    
class Cuentas(BaseModel):
    num_cuenta = models.CharField(max_length=30, verbose_name="Numero Cuenta", null=False, blank=False, unique=True)
    nombre = models.CharField(max_length=250, verbose_name="Nombre Cuenta", null=False, blank=False)
    descripcion = models.CharField(max_length=100, verbose_name="Descripcion Cuenta", null=True, blank=True, default=None)
    is_auxiliar = models.BooleanField(default=False, verbose_name="Es Auxiliar")
    nivel = models.PositiveIntegerField(verbose_name="Nivel", null=False, blank=False)
    tratamiento_especial = models.BooleanField(default=False, verbose_name="Tratamiento Especial")
    cuenta_padre = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="subcuentas")
    cuenta_tipo = models.ForeignKey(CuentasType, on_delete=models.PROTECT, null=False, blank=False, related_name="cuentas")
    
    class Meta:
        db_table = "contab_cuenta"
        verbose_name = "Cuenta"
        verbose_name_plural = "Cuentas"
        
    def __str__(self):
        return f"{self.num_cuenta} - {self.nombre}"
    
    def cuenta_to_dict(self):
        return {
            "id": self.id,
            "num_cuenta": self.num_cuenta,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "is_auxiliar": self.is_auxiliar,
            "nivel": self.nivel,
            "tratamiento_especial": self.tratamiento_especial,
            "cuenta_padre": self.cuenta_padre.id if self.cuenta_padre else None,
            "cuenta_padre_num_cuenta": self.cuenta_padre.num_cuenta if self.cuenta_padre else None,
            "cuenta_padre_nombre": self.cuenta_padre.nombre if self.cuenta_padre else None,
            "cuenta_tipo": self.cuenta_tipo.id,
            "cuenta_tipo_descripcion": self.cuenta_tipo.descripcion
        }
    
    