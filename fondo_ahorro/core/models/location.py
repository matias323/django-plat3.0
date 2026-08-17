from django.db import models

from .base import BaseModel


# ============================================================
# REGIÓN
class Region(BaseModel):
    name = models.CharField(
        verbose_name="Nombre",
        max_length=150,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "core_region"
        verbose_name = "Región"
        verbose_name_plural = "Regiones"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# COMUNA
class Commune(BaseModel):
    name = models.CharField(
        verbose_name="Nombre",
        max_length=150,
        null=False,
        blank=False,
    )

    region = models.ForeignKey(
        Region,
        verbose_name="Región",
        db_column="id_region",
        on_delete=models.PROTECT,
        related_name="communes",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "core_commune"
        verbose_name = "Comuna"
        verbose_name_plural = "Comunas"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.region.name}"