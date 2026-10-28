from django.db import models

from core.models.base import BaseModel
from core.models.document import Document
from core.models.person import Person

from .product import Product


# ============================================================
# TIPO ACTA DE ENTREGA
# ============================================================
class DeliveryRecordType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, null=False, blank=False)

    class Meta:
        db_table = "inventario_acta_entrega_tipo"
        verbose_name = "Tipo de acta de entrega"
        verbose_name_plural = "Tipos de acta de entrega"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# ESTADO ACTA DE ENTREGA
# ============================================================
class DeliveryRecordStatus(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, null=False, blank=False)

    class Meta:
        db_table = "inventario_acta_entrega_estado"
        verbose_name = "Estado de acta de entrega"
        verbose_name_plural = "Estados de acta de entrega"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# ACTA DE ENTREGA
# ============================================================
class DeliveryRecord(BaseModel):
    record_number = models.PositiveBigIntegerField(verbose_name="N° acta", unique=True, null=False, blank=False)
    record_date = models.DateField(verbose_name="Fecha acta", null=False, blank=False)
    record_type = models.ForeignKey(
        DeliveryRecordType, verbose_name="Tipo", db_column="id_record_type", related_name="records",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    status = models.ForeignKey(
        DeliveryRecordStatus, verbose_name="Estado", db_column="id_status", related_name="records",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    area = models.CharField(verbose_name="Área", max_length=255, null=False, blank=False)
    lender = models.ForeignKey(
        Person, verbose_name="Prestamista", db_column="id_lender", related_name="inventory_delivery_records",
        on_delete=models.PROTECT, null=True, blank=True,
    )
    observation = models.TextField(verbose_name="Observación", null=True, blank=True)
    registration_date = models.DateTimeField(verbose_name="Fecha registro", auto_now_add=True)

    class Meta:
        db_table = "inventario_acta_entrega"
        verbose_name = "Acta de entrega"
        verbose_name_plural = "Actas de entrega"
        ordering = ["-record_date", "-id"]

    def __str__(self):
        return f"Acta N° {self.record_number}"


# ============================================================
# ACTA DE ENTREGA - PRODUCTO
# ============================================================
class DeliveryRecordProduct(BaseModel):
    record = models.ForeignKey(
        DeliveryRecord, verbose_name="Acta", db_column="id_record", related_name="product_links",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    product = models.ForeignKey(
        Product, verbose_name="Producto", db_column="id_product", related_name="delivery_record_links",
        on_delete=models.PROTECT, null=False, blank=False,
    )
    observation = models.CharField(verbose_name="Observación", max_length=255, null=True, blank=True)

    class Meta:
        db_table = "inventario_acta_entrega_producto"
        verbose_name = "Producto de acta"
        verbose_name_plural = "Productos de acta"
        constraints = [models.UniqueConstraint(fields=["record", "product"], name="uq_inventory_record_product")]


# ============================================================
# ACTA DE ENTREGA - DOCUMENTO
# ============================================================
class DeliveryRecordDocument(BaseModel):
    record = models.ForeignKey(
        DeliveryRecord, verbose_name="Acta", db_column="id_record", related_name="document_links",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    document = models.ForeignKey(
        Document, verbose_name="Documento", db_column="id_document", related_name="inventory_record_links",
        on_delete=models.PROTECT, null=False, blank=False,
    )

    class Meta:
        db_table = "inventario_acta_entrega_documento"
        verbose_name = "Documento de acta"
        verbose_name_plural = "Documentos de acta"
        ordering = ["-id"]
