from django.db import models

from core.models.base import BaseModel
from core.models.document import Document
from core.models.person import Person

from .classification import Fund, Subclass
from .invoice import Invoice


# ============================================================
# PRODUCTO
# ============================================================
class Product(BaseModel):
    STATUS_ACTIVE = 1
    STATUS_WRITTEN_OFF = 2
    STATUS_WRITTEN_OFF_BOOK_2 = 3
    STATUS_INACTIVE = 4
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Activo"), (STATUS_WRITTEN_OFF, "De baja"),
        (STATUS_WRITTEN_OFF_BOOK_2, "De baja - Libro 2"), (STATUS_INACTIVE, "Inactivo"),
    )
    SIZE_CHOICES = (
        ("PEQUEÑO", "PEQUEÑO"), ("MEDIANO", "MEDIANO"), ("GRANDE", "GRANDE"),
        ("EXTRA GRANDE", "EXTRA GRANDE"), ("NO APLICA", "NO APLICA"),
    )

    name = models.CharField(verbose_name="Nombre producto", max_length=255, null=False, blank=False)
    brand = models.CharField(verbose_name="Marca", max_length=255, null=True, blank=True)
    model = models.CharField(verbose_name="Modelo", max_length=255, null=True, blank=True)
    size = models.CharField(verbose_name="Tamaño", max_length=30, choices=SIZE_CHOICES, null=True, blank=True)
    color = models.CharField(verbose_name="Color", max_length=100, null=True, blank=True)
    bcu_number = models.CharField(verbose_name="N° BCU", max_length=100, unique=True, null=True, blank=True)
    sap_number = models.CharField(verbose_name="N° SAP", max_length=100, unique=True, null=True, blank=True)
    role_number = models.PositiveBigIntegerField(verbose_name="N° Rol", unique=True, null=False, blank=False)
    serial_number = models.CharField(verbose_name="N° Serial", max_length=255, null=True, blank=True)
    invoice = models.ForeignKey(
        Invoice, verbose_name="Factura", db_column="id_invoice", related_name="products",
        on_delete=models.PROTECT, null=True, blank=True,
    )
    fund = models.ForeignKey(
        Fund, verbose_name="Fondo", db_column="id_fund", related_name="products",
        on_delete=models.PROTECT, null=True, blank=True,
    )
    subclass = models.ForeignKey(
        Subclass, verbose_name="Subclase", db_column="id_subclass", related_name="products",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    stock = models.PositiveIntegerField(verbose_name="Stock", default=1, null=False, blank=False)
    acquisition_date = models.DateField(verbose_name="Fecha adquisición", null=False, blank=False)
    use_start_date = models.DateField(verbose_name="Comienzo uso", null=True, blank=True)
    end_date = models.DateField(verbose_name="Fecha término", null=True, blank=True)
    initial_value = models.BigIntegerField(verbose_name="Valor inicial", default=0, null=False, blank=False)
    current_value = models.BigIntegerField(verbose_name="Valor actual", default=0, null=False, blank=False)
    depreciation = models.BigIntegerField(verbose_name="Depreciación", default=0, null=False, blank=False)
    accumulated_depreciation = models.BigIntegerField(
        verbose_name="Depreciación acumulada", default=0, null=False, blank=False,
    )
    useful_life_years = models.PositiveIntegerField(verbose_name="Vida útil años", default=0)
    useful_life_months = models.PositiveIntegerField(verbose_name="Vida útil meses", default=0)
    book = models.PositiveSmallIntegerField(verbose_name="Libro", null=True, blank=True)
    observation = models.CharField(verbose_name="Observación", max_length=255, null=True, blank=True)
    status = models.PositiveSmallIntegerField(verbose_name="Estado", choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        db_table = "inventario_producto"
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["role_number"]

    def __str__(self):
        return f"{self.role_number} - {self.name}"


# ============================================================
# ASIGNACIÓN PRODUCTO - PERSONA
# ============================================================
class ProductAssignment(BaseModel):
    person = models.ForeignKey(
        Person, verbose_name="Persona", db_column="id_person", related_name="inventory_product_assignments",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    product = models.ForeignKey(
        Product, verbose_name="Producto", db_column="id_product", related_name="assignments",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    assignment_date = models.DateField(verbose_name="Fecha asignación", null=False, blank=False)

    class Meta:
        db_table = "inventario_producto_asignado"
        verbose_name = "Asignación de producto"
        verbose_name_plural = "Asignaciones de productos"
        ordering = ["-assignment_date", "-id"]


# ============================================================
# DOCUMENTO PRODUCTO
# ============================================================
class ProductDocument(BaseModel):
    product = models.ForeignKey(
        Product, verbose_name="Producto", db_column="id_product", related_name="document_links",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    document = models.ForeignKey(
        Document, verbose_name="Documento", db_column="id_document", related_name="inventory_product_links",
        on_delete=models.PROTECT, null=False, blank=False,
    )

    class Meta:
        db_table = "inventario_producto_documento"
        verbose_name = "Documento de producto"
        verbose_name_plural = "Documentos de producto"
        ordering = ["-id"]
