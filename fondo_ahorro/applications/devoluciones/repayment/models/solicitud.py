from django.db import models
from django.conf import settings
from core.models.base import BaseModel
from .consejo import (
    DevoConsejo
)

class DevoSolicitudMotivo(BaseModel):
    descripcion = models.CharField(max_length=255)

    class Meta:
        db_table = 'devo_solicitud_motivo'
        verbose_name = 'Motivo de devolución'
        verbose_name_plural = 'Motivos de devolución'

    def __str__(self):
        return self.descripcion


class DevoSolicitudConcepto(BaseModel):
    descripcion  = models.CharField(max_length=255)

    class Meta:
        db_table = 'devo_solicitud_concepto'

    def __str__(self):
        return self.descripcion


class DevoSolicitudTipo(BaseModel):
    nombre = models.CharField(max_length=255)

    class Meta:
        db_table = 'devo_solicitud_tipo'

    def __str__(self):
        return f'Tipo de devolución {self.nombre}'


class DevoSolicitudEstado(BaseModel):
    nombre = models.CharField(max_length=255)

    class Meta:
        db_table = 'devo_solicitud_estado'

    def __str__(self):
        return f'Estado de devolución {self.nombre}'


class DevoSolicitud(BaseModel):
    tipo = models.ForeignKey(
        'DevoSolicitudTipo', on_delete=models.PROTECT, db_column='id_tipo',
        related_name='solicitudes', null=True, blank=True,
    )
    monto_general = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    direccion = models.CharField(max_length=255, blank=True, default='')
    comuna = models.ForeignKey(
        'core.Commune', on_delete=models.PROTECT, db_column='id_comuna',
        related_name='solicitudes_devolucion', null=True, blank=True,
    )
    telefono = models.CharField(max_length=30, blank=True, default='')
    correo = models.EmailField(blank=True, default='')
    motivo = models.ForeignKey(
        DevoSolicitudMotivo, on_delete=models.PROTECT,
        db_column='id_motivo', related_name='solicitudes',
        null=True, blank=True,
    )
    solicitud = models.ForeignKey(
        'core.Request', on_delete=models.PROTECT,
        db_column='id_solicitud', related_name='devoluciones',
    )
    estado = models.ForeignKey(
        DevoSolicitudEstado, on_delete=models.PROTECT,
        db_column='id_devo_solicitud_estado', related_name='solicitudes',
    )
    consejo = models.ForeignKey(
        DevoConsejo, on_delete=models.PROTECT,
        db_column='id_consejo', related_name='solicitudes',
        null=True, blank=True,
    )
    fecha_pago = models.DateField(null=True, blank=True)
    fecha_aprobacion = models.DateField(null=True, blank=True)
    grado = models.ForeignKey(
        'core.EmployeeGrade', on_delete=models.PROTECT,
        db_column='id_grado', related_name='solicitudes_devolucion',
        null=True, blank=True,
    )
    fecha_retiro = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'devo_solicitud'

    def __str__(self):
        return f'Devolución {self.pk}'


class DevoSolicitudAporte(BaseModel):
    aporte_tipo = models.ForeignKey(
        'core.PartnerContributionType', on_delete=models.PROTECT,
        db_column='id_aporte_tipo', related_name='devoluciones',
    )
    solicitud_devolucion = models.ForeignKey(
        DevoSolicitud, on_delete=models.CASCADE,
        db_column='id_devo_solicitud', related_name='aportes',
    )
    # FIJO: importe invariable. PORCENTAJE: calcular sobre el saldo vigente al pagar.
    modalidad = models.CharField(
        max_length=12, choices=[('FIJO', 'Monto fijo'), ('PORCENTAJE', 'Porcentaje')],
        default='FIJO',
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    monto = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'devo_solicitud_aporte' 

    def __str__(self):
        return f'{self.aporte_tipo}: {self.monto}'



# ============================================================
# DETALLE DE SOLICITUD DE DEVOLUCIÓN
class DevoSolicitudDetalle(BaseModel):
    solicitud_devolucion = models.ForeignKey(
        'DevoSolicitud',
        verbose_name="Solicitud de Devolución",
        on_delete=models.CASCADE,
        db_column="id_solicitud_devolucion",
        related_name="detalles",
        null=False,
        blank=False,
    )

    metodo_pago = models.ForeignKey(
        'DevoMetodoPago',
        verbose_name="Método de Pago",
        on_delete=models.PROTECT,
        db_column="id_metodo_pago",
        related_name="detalles_devolucion",
        null=False,
        blank=False,
    )

    persona = models.ForeignKey(
        'core.Person',
        verbose_name="Beneficiario",
        on_delete=models.PROTECT,
        db_column="id_persona",
        related_name="devoluciones_recibidas",
        null=False,
        blank=False,
    )

    persona_banco = models.ForeignKey(
        'core.PersonaBanco',
        verbose_name="Cuenta Bancaria",
        on_delete=models.PROTECT,
        db_column="id_persona_banco",
        related_name="devoluciones",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "devo_solicitud_detalle"
        verbose_name = "Detalle de Devolución"
        verbose_name_plural = "Detalles de Devoluciones"

    def __str__(self):
        return f"Detalle {self.pk} - {self.solicitud_devolucion}"



class DevoTipoConcepto(BaseModel):
    solicitud_concepto = models.ForeignKey(
        'DevoSolicitudConcepto', on_delete=models.PROTECT,
        db_column='id_solicitud_concepto', related_name='tipos_concepto',
    )
    solicitud_tipo = models.ForeignKey(
        'DevoSolicitudTipo', on_delete=models.PROTECT,
        db_column='id_solicitud_tipo', related_name='tipos_concepto',
    )

    class Meta:
        db_table = 'devo_tipo_concepto'

    def __str__(self):
        return f'{self.solicitud_tipo} - {self.solicitud_concepto}'


class DevoSolicitudTipoConcepto(BaseModel):
    tipo_concepto = models.ForeignKey(
        DevoTipoConcepto, on_delete=models.PROTECT,
        db_column='id_tipo_concepto', related_name='solicitudes_concepto',
    )
    solicitud_devolucion = models.ForeignKey(
        'DevoSolicitud', on_delete=models.CASCADE,
        db_column='id_solicitud_devolucion', related_name='conceptos',
    )

    class Meta:
        db_table = 'devo_solicitud_tipo_concepto'

    def __str__(self):
        return f'{self.solicitud_devolucion} - {self.tipo_concepto}'


# ============================================================
# MÉTODO DE PAGO DE DEVOLUCIONES
class DevoMetodoPago(BaseModel):
    tipo = models.CharField(
        verbose_name="Tipo de Pago",
        max_length=100,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "devo_metodo_pago"
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"
        ordering = ["tipo"]

    def __str__(self):
        return self.tipo