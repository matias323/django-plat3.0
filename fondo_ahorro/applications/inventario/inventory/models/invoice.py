from django.db import models

from core.models.base import BaseModel
from core.models.document import Document
from core.models.location import Commune
from core.models.person import Person


# ============================================================
# FACTURA
# ============================================================
class Invoice(BaseModel):
    STATUS_CURRENT = 1
    STATUS_DIGIT_ERROR = 2
    STATUS_CHOICES = ((STATUS_CURRENT, "Vigente"), (STATUS_DIGIT_ERROR, "Error digitación"))

    invoice_number = models.PositiveBigIntegerField(verbose_name="N° factura", unique=True, null=False, blank=False)
    invoice_date = models.DateField(verbose_name="Fecha factura", null=False, blank=False)

    # El proveedor puede existir en core_person, pero la factura conserva una copia de sus datos.
    # Esto replica el comportamiento del módulo 2.5 y evita crear Person incompletas.
    provider = models.ForeignKey(
        Person, verbose_name="Proveedor", db_column="id_provider", related_name="inventory_invoices",
        on_delete=models.PROTECT, null=True, blank=True,
    )
    provider_rut = models.PositiveIntegerField(verbose_name="RUT proveedor", null=True, blank=True)
    provider_dv = models.CharField(verbose_name="DV proveedor", max_length=1, null=True, blank=True)
    provider_name = models.CharField(verbose_name="Nombre proveedor", max_length=255, null=False, blank=False)

    business_activity = models.CharField(verbose_name="Giro", max_length=255, null=False, blank=False)
    commune = models.ForeignKey(
        Commune, verbose_name="Comuna", db_column="id_commune", related_name="inventory_invoices",
        on_delete=models.PROTECT, null=True, blank=True,
    )
    address = models.CharField(verbose_name="Dirección", max_length=255, null=False, blank=False)
    address_number = models.CharField(verbose_name="Número", max_length=30, null=True, blank=True)
    address_block = models.CharField(verbose_name="Dpto./Oficina/etc.", max_length=255, null=True, blank=True)
    phone = models.CharField(verbose_name="Teléfono", max_length=20, null=True, blank=True)
    email = models.EmailField(verbose_name="Correo", max_length=255, null=True, blank=True)

    net_amount = models.BigIntegerField(verbose_name="Monto", default=0, null=False, blank=False)
    vat_amount = models.BigIntegerField(verbose_name="IVA", default=0, null=False, blank=False)
    payment_date = models.DateField(verbose_name="Fecha pago", null=True, blank=True)
    status = models.PositiveSmallIntegerField(verbose_name="Estado", choices=STATUS_CHOICES, default=STATUS_CURRENT)

    class Meta:
        db_table = "inventario_factura"
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ["-invoice_date", "-id"]

    def __str__(self):
        return f"Factura N° {self.invoice_number}"

    @property
    def commune_name(self):
        return self.commune.name if self.commune_id else ""

    @property
    def formatted_provider_rut(self):
        rut = f"{int(self.provider_rut):,}".replace(",", ".") if self.provider_rut else ""
        return f"{rut}-{self.provider_dv}" if rut else ""


# ============================================================
# DOCUMENTO FACTURA
# ============================================================
class InvoiceDocument(BaseModel):
    invoice = models.ForeignKey(
        Invoice, verbose_name="Factura", db_column="id_invoice", related_name="document_links",
        on_delete=models.CASCADE, null=False, blank=False,
    )
    document = models.ForeignKey(
        Document, verbose_name="Documento", db_column="id_document", related_name="inventory_invoice_links",
        on_delete=models.PROTECT, null=False, blank=False,
    )

    class Meta:
        db_table = "inventario_factura_documento"
        verbose_name = "Documento de factura"
        verbose_name_plural = "Documentos de factura"
        ordering = ["-id"]
