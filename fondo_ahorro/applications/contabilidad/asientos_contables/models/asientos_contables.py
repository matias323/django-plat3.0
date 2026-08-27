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
    
class AsientoContableTipo(BaseModel):
    description = models.CharField(max_length=50, null=False, blank=False, verbose_name="Descripción")
    
    def __str__(self):
        return self.description
    
    class Meta:
        db_table = "contab_asiento_tipo"
        verbose_name = "Tipo de Asiento Contable"
        verbose_name_plural = "Tipos de Asientos Contables"

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
            "periodo": self.period,
            "periodo_estado": self.period.is_active,
            "user_create": self.user_create.person.get_name(),
            "movimientos": [
                movimientos.movimiento_to_dict() for movimientos in self.movimientos.all()
            ],
            "origen": self.get_origen_to_dict()
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
            "asiento": self.entry,
            "cuenta": self.account,
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
            "movimiento_id": self.movement.id,
            "persona": self.person.get_full_name(),
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

