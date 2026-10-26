from django.db import models

from core.models.base import BaseModel


# ============================================================
# FONDO
# ============================================================
class Fund(BaseModel):
    name = models.CharField(verbose_name="Fondo", max_length=100, null=False, blank=False)

    class Meta:
        db_table = "inventory_fund"
        verbose_name = "Fondo"
        verbose_name_plural = "Fondos"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# CLASE DE ACTIVO
# ============================================================
class AssetClass(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "inventory_asset_class"
        verbose_name = "Clase de activo"
        verbose_name_plural = "Clases de activo"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# CLASE
# ============================================================
class InventoryClass(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "inventory_class"
        verbose_name = "Clase"
        verbose_name_plural = "Clases"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# SUBCLASE
# ============================================================
class Subclass(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)
    useful_life_years = models.PositiveIntegerField(verbose_name="Vida útil años", null=False, blank=False)
    inventory_class = models.ForeignKey(
        InventoryClass, verbose_name="Clase", db_column="id_inventory_class", related_name="subclasses",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    asset_class = models.ForeignKey(
        AssetClass, verbose_name="Clase de activo", db_column="id_asset_class", related_name="subclasses",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    accounting_account_id = models.PositiveBigIntegerField(verbose_name="Cuenta contable", null=True, blank=True)

    class Meta:
        db_table = "inventory_subclass"
        verbose_name = "Subclase"
        verbose_name_plural = "Subclases"
        ordering = ["asset_class__name", "inventory_class__name", "name"]

    def __str__(self):
        return f"{self.asset_class} / {self.inventory_class} / {self.name}"
