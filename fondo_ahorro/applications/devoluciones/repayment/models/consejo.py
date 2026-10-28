from django.db import models
from django.conf import settings
from core.models.base import BaseModel

class DevoConsejo(BaseModel):
    estado = models.BooleanField(default=True)
    fecha_consejo = models.DateField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'devo_consejo'
        ordering = ['-fecha_consejo']

    def __str__(self):
        return f'Consejo {self.pk} - {self.fecha_consejo}'
