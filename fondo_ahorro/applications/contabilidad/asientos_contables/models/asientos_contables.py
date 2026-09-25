from django.db import models
from core.models.base import BaseModel
from core.models.person import Person
from applications.contabilidad.periodo_contable.models import PeriodoContable
from applications.contabilidad.plan_cuentas.models import Cuentas

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AsientoContableEstado(BaseModel):
    description = models.CharField(max_length=50, null=False, blank=False, verbose_name="Descripción")
    
    def __str__(self):
        return self.description
    
    class Meta:
        db_table = "contab_asiento_estado"
        verbose_name = "Estado de Asiento Contable"
        verbose_name_plural = "Estados de Asientos Contables"
        
    #estados
    def estados():
        return AsientoContableEstado.objects.filter(is_active=True)
    
class AsientoContableTipo(BaseModel):
    description = models.CharField(max_length=50, null=False, blank=False, verbose_name="Descripción")
    
    def __str__(self):
        return self.description
    
    class Meta:
        db_table = "contab_asiento_tipo"
        verbose_name = "Tipo de Asiento Contable"
        verbose_name_plural = "Tipos de Asientos Contables"
        
    #tipos de asiento(ingreso manual)
    def ingreso_manual():
        return AsientoContableTipo.objects.filter(pk=6, is_active=True)
    
    #tipos de asiento(todos)
    def todos():
        return AsientoContableTipo.objects.filter(is_active=True)

class AsientoContable(BaseModel):
    entry_number = models.PositiveIntegerField(null=False, blank=False, verbose_name="Número Asiento")
    entry_year = models.PositiveIntegerField(verbose_name="Año Asiento")
    entry_date = models.DateField(null=False, blank=False, verbose_name="Fecha Asiento")
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name="Glosa Asiento")
    voucher_number = models.CharField(max_length=20, null=False, blank=False, verbose_name="Número Comprobante")
    status = models.ForeignKey(AsientoContableEstado, 
                               on_delete=models.PROTECT, 
                               null=False, 
                               blank=False, 
                               verbose_name="Estado Asiento Contable")
    entry_type = models.ForeignKey(AsientoContableTipo, 
                                   on_delete=models.PROTECT, 
                                   null=False, 
                                   blank=False, 
                                   verbose_name="Tipo Asiento Contable")
    period = models.ForeignKey(PeriodoContable, 
                               on_delete=models.PROTECT, 
                               null=False, blank=False, 
                               verbose_name="Periodo Contable", 
                               related_name="asientos")
    origin_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Tipo de Origen")
    origin_object_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="ID de Origen")
    origin = GenericForeignKey("origin_content_type", "origin_object_id")
    is_null = models.BooleanField(default=False, verbose_name="Es Nulo")
    version = models.PositiveBigIntegerField(null=False, blank=False, default=1, verbose_name="Versión")
    
    class Meta:
        db_table = "contab_asiento"
        verbose_name = "Asiento Contable"
        verbose_name_plural = "Asientos Contables"
        ordering = ["-entry_date"]
        constraints = [
            models.UniqueConstraint(fields=["entry_number", "entry_year"], name="unique_asiento_numero_anio"),
        ]
        
    def __str__(self):
        return f"{self.voucher_number} - {self.period}"
    
    def get_origen_to_dict(self):
        if not self.origin:
            return None
        
        return {
            "id": self.origin_object_id,
            "app": self.origin_content_type.app_label,
            "tipo": self.origin_content_type.model
        }
    
    def asiento_to_dict(self):
        movimientos_data = []
        
        for movimiento in self.movimientos.all():
            auxiliares_data = []
            
            for auxiliar in movimiento.auxiliares.all():
                auxiliares_data.append(auxiliar.auxiliar_to_dict())
            
            movimiento_data = movimiento.movimiento_to_dict()
            movimiento_data["auxiliares"] = auxiliares_data
            movimientos_data.append(movimiento_data)
        
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            "numero_asiento": self.entry_number,
            "fecha_asiento": self.entry_date,
            "anio_asiento": self.entry_year,
            "glosa": self.description,
            "numero_comprobante": self.voucher_number,
            "asiento_estado": self.status.description,
            "asiento_tipo": self.entry_type.description,
            "id_asiento_tipo" : self.entry_type.id,
            "periodo": self.period.periodo_to_dict(),
            "user_create": self.user_create.person.get_name(),
            "movimientos": movimientos_data,
            "origen": self.get_origen_to_dict(),
            "is_null": self.is_null,
            "version": self.version,
            "aprobacion": self.aprobaciones.exists()
        }
        
class AsientoMovimiento(BaseModel):
    entry = models.ForeignKey(
        AsientoContable, 
        on_delete=models.PROTECT, 
        null=False, blank=False, 
        verbose_name="Asiento Contable", 
        related_name="movimientos")
    account = models.ForeignKey(Cuentas, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Cuenta Contable")
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name="Glosa Movimiento")
    debit = models.PositiveBigIntegerField(null=False, blank=False, default=0, verbose_name="Debe")
    credit = models.PositiveBigIntegerField(null=False, blank=False, default=0, verbose_name="Haber")
    
    class Meta:
        db_table = "contab_movimiento"
        verbose_name = "Movimiento Contable"
        verbose_name_plural = "Movimientos Contables"
        
    def __str__(self):
        return f"{self.entry} - {self.account}"
    
    def movimiento_to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            # "asiento": self.entry.asiento_to_dict(), #genera error de recursion infinita
            "cuenta": self.account.cuenta_to_dict(),
            "glosa": self.description,
            "debe": self.debit,
            "haber": self.credit,
            "user_create": self.user_create.person.get_name(),
            "auxiliares": [
                auxiliares.auxiliar_to_dict() for auxiliares in self.auxiliares.all()
            ]
        }

class AsientoMovimientoAux(BaseModel):
    movement = models.ForeignKey(
        AsientoMovimiento, 
        on_delete=models.PROTECT, 
        null=False, 
        blank=False, 
        verbose_name="Movimiento Contable", 
        related_name="auxiliares")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Persona")
    amount = models.PositiveBigIntegerField(null=False, blank=False, verbose_name="Monto")
    
    class Meta:
        db_table = "contab_movimiento_aux"
        verbose_name = "Movimiento Contable Auxiliar"
        verbose_name_plural = "Movimientos Contables Auxiliares"
        
        constraints = [
            models.UniqueConstraint(fields=["movement", "person"], name="unique_movimiento_persona"),
        ]
    
    def __str__(self):
        return f"{self.person.get_full_name()} - {self.amount}"
    
    def auxiliar_to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            # "movimiento": self.movement.movimiento_to_dict(), #genera error de recursion infinita
            "nombre_persona": self.person.get_full_name(),
            "rut": self.person.get_rut(),
            "id_persona": self.person.id,
            "monto": self.amount,
            "user_create": self.user_create.person.get_name(),
        }

class AsientoContableCorrelativo(BaseModel):
    year = models.PositiveIntegerField(verbose_name="Año", null=False, blank=False, unique=True)
    last_number = models.PositiveIntegerField(verbose_name="Último Número", null=False, blank=False)
    
    class Meta:
        db_table = "contab_asiento_correlativo"
        verbose_name = "Correlativo Asiento Contable"
        verbose_name_plural = "Correlativos Asientos Contables"
        
    def __str__(self):
        return f"{self.year} - {self.last_number}"
    
class AsientoContableAprobacion(BaseModel):
    entry = models.ForeignKey(
            AsientoContable, 
            on_delete=models.PROTECT, 
            null=False, blank=False, 
            verbose_name="Asiento Contable", 
            related_name="aprobaciones")
    
    class Meta:
        db_table = "contab_asiento_aprobacion"
        verbose_name = "Aprobación Asiento Contable"
        verbose_name_plural = "Aprobaciones Asientos Contables"
        
    def __str__(self):
        return f"{self.entry} - {self.user_create.person.get_name()}"
    
class AsientoContableBloqueo(BaseModel):
    entry = models.ForeignKey(AsientoContable, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Asiento Contable", related_name="bloqueo")
    locked_at = models.DateTimeField(auto_now_add=True, null=False, blank=False, verbose_name="Fecha Bloqueo")
    class Meta:
        db_table = "contab_asiento_bloqueo"
        verbose_name = "Bloqueo Asiento Contable"
        verbose_name_plural = "Bloqueos Asientos Contables"
        
    #retornar el nombre de la persona que tiene el bloqueo
    def get_user_bloqueo(self):
        if not self.user_create:
            return "Usuario desconocido"
        
        return self.user_create.person.get_full_name()
            

