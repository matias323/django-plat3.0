from django.conf import settings
from django.db import models
from core.models.base import BaseModel
from pathlib import Path


# ============================================================
# COMPATIBILIDAD CON MIGRACIONES ANTIGUAS
def ruta_documento(instance, filename):
    """
    Función histórica utilizada por las migraciones 0005 y 0006.

    Se conserva para permitir que Django cargue correctamente
    las migraciones anteriores.

    Los nuevos documentos se almacenan mediante core.Document.
    """
    nombre = Path(filename).name
    solicitud_id = getattr(instance, "solicitud_id", None) or "sin_solicitud"

    return f"devoluciones/{solicitud_id}/{nombre}"


class DevoDocumentoTipo(BaseModel):
    codigo = models.SlugField(max_length=60, unique=True)
    nombre = models.CharField(max_length=150)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'devo_documento_tipo'
        ordering = ['orden', 'pk']

    def __str__(self):
        return self.nombre


class DevoDocumento(BaseModel):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        APROBADO = 'aprobado', 'Aprobado'
        RECHAZADO = 'rechazado', 'Rechazado'

    solicitud = models.ForeignKey(
        'DevoSolicitud', on_delete=models.PROTECT,
        related_name='documentos', db_column='id_devo_solicitud',
    )
    tipo = models.ForeignKey(
        DevoDocumentoTipo, on_delete=models.PROTECT,
        related_name='documentos', db_column='id_tipo_documento',
    )
    document = models.ForeignKey(
        'core.Document', on_delete=models.PROTECT,
        db_column='id_document', related_name='documentos_devolucion',
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    rejection_comment = models.TextField(null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='id_validated_by', related_name='validated_devo_documents',
        null=True, blank=True,
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'devo_documento'
        ordering = ['-pk']

    def __str__(self):
        return f'{self.tipo} - {self.document.document_name}'


class DevoObservacion(BaseModel):
    class Accion(models.TextChoices):
        SOLICITUD_CREADA = 'solicitud_creada', 'Solicitud creada'
        ESTADO_SOLICITUD = 'estado_solicitud', 'Estado de solicitud'
        CONSEJO = 'consejo', 'Consejo actualizado'
        DOCUMENTO_ADJUNTADO = 'documento_adjuntado', 'Documento adjuntado'
        DOCUMENTO_REEMPLAZADO = 'documento_reemplazado', 'Documento reemplazado'
        DOCUMENTO_ELIMINADO = 'documento_eliminado', 'Documento eliminado'
        ESTADO_DOCUMENTO = 'estado_documento', 'Estado de documento'
        COMENTARIO = 'comentario', 'Comentario'  # Se conserva por historial; no se expone para uso manual.

    solicitud = models.ForeignKey(
        'DevoSolicitud', on_delete=models.PROTECT,
        related_name='observaciones', db_column='id_devo_solicitud',
    )
    documento = models.ForeignKey(
        DevoDocumento, on_delete=models.PROTECT,
        related_name='observaciones', db_column='id_documento', null=True, blank=True,
    )
    accion = models.CharField(max_length=35, choices=Accion.choices)
    descripcion = models.TextField()

    class Meta:
        db_table = 'devo_observacion'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.get_accion_display()} - solicitud {self.solicitud_id}'
