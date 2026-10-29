from django.db import models
from core.models.base import BaseModel


class DevoConsejoEstado(BaseModel):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'devo_consejo_estado'
        verbose_name = 'Estado de consejo'
        verbose_name_plural = 'Estados de consejo'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class DevoConsejo(BaseModel):
    estado = models.ForeignKey(
        DevoConsejoEstado, on_delete=models.PROTECT,
        db_column='estado', related_name='consejos',
    )
    fecha_consejo = models.DateField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'devo_consejo'
        ordering = ['-fecha_consejo']

    def __str__(self):
        return f'Consejo {self.pk} - {self.fecha_consejo}'
