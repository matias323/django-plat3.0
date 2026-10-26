<<<<<<< HEAD
=======
# from django.db import models
# from django.conf import settings
# from core.models.base import BaseModel


# class DevoSolicitudMotivo(BaseModel):
#     descripcion = models.CharField(max_length=255)

#     class Meta:
#         db_table = 'devo_solicitud_motivo'
#         verbose_name = 'Motivo de devolución'
#         verbose_name_plural = 'Motivos de devolución'

#     def __str__(self):
#         return self.descripcion


# class DevoSolicitudConcepto(BaseModel):
#     descripcion  = models.CharField(max_length=255)

#     class Meta:
#         db_table = 'devo_solicitud_concepto'

#     def __str__(self):
#         return self.descripcion


# class DevoSolicitudTipo(BaseModel):
#     nombre = models.CharField(max_length=255)

#     class Meta:
#         db_table = 'devo_solicitud_tipo'

#     def __str__(self):
#         return f'Tipo de devolución {self.id_tipo}'


# class DevoSolicitudEstado(BaseModel):
#     nombre = models.CharField(max_length=255)

#     class Meta:
#         db_table = 'devo_solicitud_estado'

#     def __str__(self):
#         return f'Estado de devolución {self.id_estado}'


# class DevoConsejo(BaseModel):
#     estado = models.BooleanField(default=True)
#     fecha_consejo = models.DateField()
#     fecha_creacion = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         db_table = 'devo_consejo'
#         ordering = ['-fecha_consejo']

#     def __str__(self):
#         return f'Consejo {self.pk} - {self.fecha_consejo}'


# class DevoSolicitud(BaseModel):
#     motivo = models.ForeignKey(
#         DevoSolicitudMotivo, on_delete=models.PROTECT,
#         db_column='id_motivo', related_name='solicitudes',
#         null=True, blank=True,
#     )
#     solicitud = models.ForeignKey(
#         'core.Request', on_delete=models.PROTECT,
#         db_column='id_solicitud', related_name='devoluciones',
#     )
#     estado = models.ForeignKey(
#         DevoSolicitudEstado, on_delete=models.PROTECT,
#         db_column='id_devo_solicitud_estado', related_name='solicitudes',
#     )
#     consejo = models.ForeignKey(
#         DevoConsejo, on_delete=models.PROTECT,
#         db_column='id_consejo', related_name='solicitudes',
#         null=True, blank=True,
#     )
#     fecha_pago = models.DateField(null=True, blank=True)
#     fecha_aprobacion = models.DateField(null=True, blank=True)
#     grado = models.ForeignKey(
#         'core.EmployeeGrade', on_delete=models.PROTECT,
#         db_column='id_grado', related_name='solicitudes_devolucion',
#         null=True, blank=True,
#     )
#     fecha_retiro = models.DateField(null=True, blank=True)

#     class Meta:
#         db_table = 'devo_solicitud'

#     def __str__(self):
#         return f'Devolución {self.pk}'


# class DevoTipoConcepto(BaseModel):
#     solicitud_concepto = models.ForeignKey(
#         DevoSolicitudConcepto, on_delete=models.PROTECT,
#         db_column='id_solicitud_concepto', related_name='tipos_concepto',
#     )
#     solicitud_tipo = models.ForeignKey(
#         DevoSolicitudTipo, on_delete=models.PROTECT,
#         db_column='id_solicitud_tipo', related_name='tipos_concepto',
#     )

#     class Meta:
#         db_table = 'devo_tipo_concepto'

#     def __str__(self):
#         return f'{self.solicitud_tipo} - {self.solicitud_concepto}'


# class DevoSolicitudTipoConcepto(BaseModel):
#     tipo_concepto = models.ForeignKey(
#         DevoTipoConcepto, on_delete=models.PROTECT,
#         db_column='id_tipo_concepto', related_name='solicitudes_concepto',
#     )
#     solicitud_devolucion = models.ForeignKey(
#         DevoSolicitud, on_delete=models.CASCADE,
#         db_column='id_solicitud_devolucion', related_name='conceptos',
#     )

#     class Meta:
#         db_table = 'devo_solicitud_tipo_concepto'

#     def __str__(self):
#         return f'{self.solicitud_devolucion} - {self.tipo_concepto}'


# class DevoSolicitudAporte(BaseModel):
#     aporte_tipo = models.ForeignKey(
#         'core.PartnerContributionType', on_delete=models.PROTECT,
#         db_column='id_aporte_tipo', related_name='devoluciones',
#     )
#     solicitud_devolucion = models.ForeignKey(
#         DevoSolicitud, on_delete=models.CASCADE,
#         db_column='id_devo_solicitud', related_name='aportes',
#     )
#     monto = models.DecimalField(max_digits=15, decimal_places=2)

#     class Meta:
#         db_table = 'devo_solicitud_aporte'

#     def __str__(self):
#         return f'{self.aporte_tipo}: {self.monto}'


# class DevoSolicitudDetalle(BaseModel):
#     solicitud_devolucion = models.ForeignKey(
#         DevoSolicitud, on_delete=models.CASCADE,
#         db_column='id_solicitud_devolucion', related_name='detalles',
#     )
#     # Estos dos campos son provisionales: el ERD contiene referencias
#     # a tes_metodo_pago y persona_banco, cuyos modelos no fueron adjuntados.
#     id_metodo_pago = models.PositiveBigIntegerField()
#     persona = models.ForeignKey(
#         'core.Person', on_delete=models.PROTECT,
#         db_column='id_persona', related_name='devoluciones_recibidas',
#     )
#     id_persona_banco = models.PositiveBigIntegerField(null=True, blank=True)

#     class Meta:
#         db_table = 'devo_solicitud_detalle'

#     def __str__(self):
#         return f'Detalle {self.pk} - {self.solicitud_devolucion}'
>>>>>>> felipe
