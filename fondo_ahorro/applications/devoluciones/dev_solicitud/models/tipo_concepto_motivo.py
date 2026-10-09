
from django.db import models
# Create your models here.

from core.models.base import BaseModel




class TipoDevolucion(BaseModel):
    name = models.CharField(
                        max_length=255,
                        null=False,
                        blank=False,
                        verbose_name="Nombre/Descripción",
                        )

    class Meta:
        db_table="devo_solicitud_tipo"

    def __str__(self,):
        return f"{self.name}"

class ConceptoDevolucion(BaseModel):
    name= models.CharField(
                        max_length=255,
                        null=False,
                        blank=False,
                        verbose_name="Nombre/Descripción",
                        )
    class Meta:
        db_table="devo_solicitud_concepto"
    def __str__(self,):
        return f"{self.name}"

class TipoConceptoDevolucion(BaseModel):
    tipo = models.ForeignKey(
                            TipoDevolucion,
                            on_delete=models.PROTECT,
                            verbose_name="Tipo de Devolucion",
                            )
    concepto = models.ForeignKey(
                                ConceptoDevolucion,
                                on_delete=models.PROTECT,
                                verbose_name="Concepto de Devolucion",
                                )

    class Meta:
        db_table="devo_solicitud_tipo_concepto"
    def __str__(self,):
        return f"Tipo: {self.tipo} | Concepto: {self.concepto}"

class EstadoDevolucion(BaseModel):
    name= models.CharField(
                            max_length=255,
                            null=False,
                            blank=False,
                            verbose_name="Nombre/Descripción",
                            )
    class Meta:
        db_table="devo_solicitud_estado"

    def __str__(self,):
        return f"{self.name}"

class MotivoDevolucion(BaseModel):
    name= models.CharField(
                            max_length=255,
                            null=False,
                            blank=False,
                            verbose_name="Nombre/Descripción",
                            )

    class Meta:
        db_table="devo_solicitud_motivo"

    def __str__(self,):
        return f"{self.name}"