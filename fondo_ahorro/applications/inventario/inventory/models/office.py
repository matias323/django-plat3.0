from django.db import models

from core.models.base import BaseModel
from core.models.person import Person

from .product import Product


# ============================================================
# OFICINA
# ============================================================
class Office(BaseModel):
    name = models.CharField(verbose_name="Oficina", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "inventory_office"
        verbose_name = "Oficina"
        verbose_name_plural = "Oficinas"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# OFICINA - PERSONA
# ============================================================
class OfficePerson(BaseModel):
    office = models.ForeignKey(
        Office, verbose_name="Oficina", db_column="id_office", related_name="person_links",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    person = models.ForeignKey(
        Person, verbose_name="Persona", db_column="id_person", related_name="inventory_office_links",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    assignment_date = models.DateField(verbose_name="Fecha", null=False, blank=False)

    class Meta:
        db_table = "inventory_office_person"
        verbose_name = "Persona de oficina"
        verbose_name_plural = "Personas de oficina"
        constraints = [models.UniqueConstraint(fields=["office", "person"], name="uq_inventory_office_person")]


# ============================================================
# OFICINA - PRODUCTO
# ============================================================
class OfficeProduct(BaseModel):
    office = models.ForeignKey(
        Office, verbose_name="Oficina", db_column="id_office", related_name="product_links",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    product = models.OneToOneField(
        Product, verbose_name="Producto", db_column="id_product", related_name="office_link",
        on_delete=models.CASCADE, null=False, blank=False,
    )

    class Meta:
        db_table = "inventory_office_product"
        verbose_name = "Producto de oficina"
        verbose_name_plural = "Productos de oficina"
