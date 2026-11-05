from django.db import models

from core.models.base import BaseModel
from core.models.document import Document
from core.models.partner import PartnerContributionType

from .loan import Loan, LoanInstallment


# ============================================================
# TIPO DE PAGO
class LoanPaymentType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "pago_prestamo_tipo"
        verbose_name = "Pago Préstamo Tipo"
        verbose_name_plural = "Pago Préstamo Tipos"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# ESTADO DE PAGO
class LoanPaymentStatus(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "pago_prestamo_estado"
        verbose_name = "Pago de Préstamo Estado"
        verbose_name_plural = "Pago de Préstamo Estados"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# PAGO DE PRESTAMO
class LoanPayment(BaseModel):
    installment = models.ForeignKey(
        LoanInstallment,
        verbose_name="Cuota",
        db_column="id_installment",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )

    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
        on_delete=models.PROTECT,
        related_name="payments",
        null=False,
        blank=False,
    )

    payment_type = models.ForeignKey(
        LoanPaymentType,
        verbose_name="Tipo de Pago",
        db_column="id_payment_type",
        on_delete=models.PROTECT,
        related_name="payments",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)

    previous_balance = models.DecimalField(
        verbose_name="Saldo Anterior",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    previous_installment = models.DecimalField(
        verbose_name="Cuota Anterior",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    status_changed_at = models.DateTimeField(verbose_name="Fecha de Cambio de Estado", null=False, blank=False)
    ip = models.GenericIPAddressField(verbose_name="Dirección IP", null=False, blank=False)

    status = models.ForeignKey(
        LoanPaymentStatus,
        verbose_name="Estado",
        db_column="id_status",
        on_delete=models.PROTECT,
        related_name="payments",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "pago_prestamo"
        verbose_name = "Pago de Préstamo"
        verbose_name_plural = "Pagos de Préstamo"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pago {self.id} - {self.loan}"


# ============================================================
# REVERSA DE PAGO
class LoanPaymentReversal(BaseModel):
    payment = models.ForeignKey(
        LoanPayment,
        verbose_name="Pago",
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="reversals",
        null=False,
        blank=False,
    )

    reason = models.CharField(verbose_name="Motivo", max_length=255, null=False, blank=False)

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_payment_reversals",
        null=True,
        blank=True,
    )

    ip = models.GenericIPAddressField(verbose_name="Dirección IP", null=False, blank=False)

    deposit_contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Aporte Destino del Depósito",
        db_column="id_deposit_contribution_type",
        on_delete=models.PROTECT,
        related_name="loan_payment_reversal_deposits",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "pago_prestamo_reversa"
        verbose_name = "Pago Reversa"
        verbose_name_plural = "Pago Reversas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reversa {self.id} - {self.payment}"


# ============================================================
# APORTE EN PAGO
class LoanPaymentContribution(BaseModel):
    payment = models.ForeignKey(
        LoanPayment,
        verbose_name="Pago",
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="contributions",
        null=False,
        blank=False,
    )

    contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Tipo de Aporte",
        db_column="id_contribution_type",
        on_delete=models.PROTECT,
        related_name="loan_payments",
        null=False,
        blank=False,
    )

    contribution_amount = models.DecimalField(
        verbose_name="Monto del Aporte",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
    )

    previous_contribution_balance = models.DecimalField(
        verbose_name="Saldo de Aporte Anterior",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "pago_prestamo_aporte"
        verbose_name = "Pago de Préstamo Aporte"
        verbose_name_plural = "Pagos de Préstamo Aportes"
        ordering = ["id"]

    def __str__(self):
        return f"{self.payment} - {self.contribution_type}"


# ============================================================
# DOCUMENTO DE PAGO
class LoanPaymentDocument(BaseModel):
    payment = models.ForeignKey(
        LoanPayment,
        verbose_name="Pago",
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="documents",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_payment_documents",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "pago_prestamo_documento"
        verbose_name = "Pago Documento"
        verbose_name_plural = "Pago Documentos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.payment} - {self.document}"


# ============================================================
# DEPOSITO DE PAGO
class LoanPaymentDeposit(BaseModel):
    payment = models.ForeignKey(
        LoanPayment,
        verbose_name="Pago",
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="deposits",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(
        verbose_name="Monto",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_payment_deposits",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "pago_prestamo_deposito"
        verbose_name = "Pago Deposito"
        verbose_name_plural = "Pago Depósitos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.payment} - {self.amount}"


# ============================================================
# METODO DE PAGO EXTRASISTEMA
class LoanPaymentExternalMethod(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "pago_prestamo_extrasistema_metodo"
        verbose_name = "Método de Pago Extrasistema"
        verbose_name_plural = "Métodos de Pago Extrasistema"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# PAGO EXTRASISTEMA
class LoanPaymentExternal(BaseModel):
    payment = models.ForeignKey(
        LoanPayment,
        verbose_name="Pago",
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="external_payments",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)

    method = models.ForeignKey(
        LoanPaymentExternalMethod,
        verbose_name="Método",
        db_column="id_method",
        on_delete=models.PROTECT,
        related_name="external_payments",
        null=False,
        blank=False,
    )

    contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Tipo de Aporte",
        db_column="id_contribution_type",
        on_delete=models.PROTECT,
        related_name="external_loan_payments",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "pago_prestamo_extrasistema"
        verbose_name = "Pago Extrasistema"
        verbose_name_plural = "Pagos Extrasistema"
        ordering = ["id"]

    def __str__(self):
        return f"{self.payment} - {self.amount}"


# ============================================================
# DOCUMENTO DE PAGO EXTRASISTEMA
class LoanPaymentExternalDocument(BaseModel):
    external_payment = models.ForeignKey(
        LoanPaymentExternal,
        verbose_name="Pago Extrasistema",
        db_column="id_external_payment",
        on_delete=models.PROTECT,
        related_name="documents",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="external_loan_payment_documents",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "pago_prestamo_extrasistema_documento"
        verbose_name = "Pago Extrasistema Documento"
        verbose_name_plural = "Pago Extrasistema Documentos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.external_payment} - {self.document}"


# ============================================================
# TIPO DE NUMERO DE DOCUMENTO
class LoanDocumentNumberType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "pago_prestamo_tipo_numero_documento"
        verbose_name = "Tipo de Número de Documento"
        verbose_name_plural = "Tipos de Número de Documento"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# NUMERO DE DOCUMENTO
class LoanDocumentNumber(BaseModel):
    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_numbers",
        null=False,
        blank=False,
    )

    number_type = models.ForeignKey(
        LoanDocumentNumberType,
        verbose_name="Tipo de Número",
        db_column="id_number_type",
        on_delete=models.PROTECT,
        related_name="document_numbers",
        null=False,
        blank=False,
    )

    number = models.BigIntegerField(verbose_name="Número", null=True, blank=True)

    class Meta:
        db_table = "pago_prestamo_numero_documento"
        verbose_name = "Número de Documento"
        verbose_name_plural = "Números de Documento"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "number_type"],
                name="unique_loan_document_number_type",
            ),
        ]

    def __str__(self):
        return f"{self.document} - {self.number_type}: {self.number}"