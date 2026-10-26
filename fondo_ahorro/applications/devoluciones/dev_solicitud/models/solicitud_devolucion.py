
from django.db import models
# Create your models here.

from core.models.base import BaseModel
from core.models.request import Request

from core.models.partner import Partner

from .tipo_concepto_motivo import MotivoDevolucion, EstadoDevolucion


class Devolucion(BaseModel):

    request = models.ForeignKey(
                            Request,
                            on_delete=models.PROTECT,
                            verbose_name="Core Solicitud",
                            )


    socio  = models.ForeignKey(
                            Partner,
                            on_delete=models.PROTECT,
                            verbose_name="Socio",
                            )

    


    class Meta:
        db_table="dev_solicitud"

    def __str__(self):
        return f""



