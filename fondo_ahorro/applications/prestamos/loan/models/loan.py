from django.db import models

from core.models.base import BaseModel
from core.models.document import Document, DocumentType
from core.models.observation import Observation
from core.models.person import Person, PersonDiprecaCode
from core.models.request import Request


# ============================================================
# TIPO DE PRESTAMO : id_tipo_prestamo
class LoanType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, null=False, blank=False)

    class Meta:
        db_table = "loan_type"
        verbose_name = "Tipo de Préstamo"
        verbose_name_plural = "Tipos de Préstamo"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# CONCEPTO DE PRESTAMO
class LoanConcept(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "loan_concept"
        verbose_name = "Concepto de Préstamo"
        verbose_name_plural = "Conceptos de Préstamo"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# TIPO DE PRESTAMO CONCEPTO : id_tipo_concepto
class LoanTypeConcept(BaseModel):
    loan_type = models.ForeignKey(
        LoanType,
        verbose_name="Tipo de Préstamo",
        db_column="id_loan_type",
        on_delete=models.PROTECT,
        related_name="type_concepts",
        null=False,
        blank=False,
    )

    concept = models.ForeignKey(
        LoanConcept,
        verbose_name="Concepto",
        db_column="id_concept",
        on_delete=models.PROTECT,
        related_name="type_concepts",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "loan_type_concept"
        verbose_name = "Concepto de Tipo de Préstamo"
        verbose_name_plural = "Conceptos de Tipos de Préstamo"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["loan_type", "concept"], name="unique_loan_type_concept"),
        ]

    def __str__(self):
        return f"{self.loan_type} - {self.concept}"


# ============================================================
# TASA DE PRESTAMO
class LoanRate(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, null=False, blank=False)

    rate = models.DecimalField(
        verbose_name="Tasa",
        max_digits=8,
        decimal_places=4,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "loan_rate"
        verbose_name = "Tasa de Préstamo"
        verbose_name_plural = "Tasas de Préstamo"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} - {self.rate}%"


# ============================================================
# ESTADO DE PRESTAMO
class LoanStatus(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "loan_status"
        verbose_name = "Estado de Préstamo"
        verbose_name_plural = "Estados de Préstamo"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# METODO DE COBRO
class LoanCollectionMethod(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "loan_collection_method"
        verbose_name = "Método de Cobro"
        verbose_name_plural = "Métodos de Cobro"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# PRESTAMO
class Loan(BaseModel):
    request = models.ForeignKey(
        Request,
        verbose_name="Solicitud",
        db_column="id_request",
        on_delete=models.PROTECT,
        related_name="loans",
        null=True,
        blank=True,
    )

    loan_type = models.ForeignKey(
        LoanType,
        verbose_name="Tipo de Préstamo",
        db_column="id_loan_type",
        on_delete=models.PROTECT,
        related_name="loans",
        null=False,
        blank=False,
    )

    type_concept = models.ForeignKey(
        LoanTypeConcept,
        verbose_name="Concepto de Tipo",
        db_column="id_type_concept",
        on_delete=models.PROTECT,
        related_name="loans",
        null=False,
        blank=False,
    )

    person = models.ForeignKey(
        Person,
        verbose_name="Beneficiario",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="loans",
        null=False,
        blank=False,
    )

    collection_method = models.ForeignKey(
        LoanCollectionMethod,
        verbose_name="Método de Cobro",
        db_column="id_collection_method",
        on_delete=models.PROTECT,
        related_name="loans",
        null=False,
        blank=False,
    )

    rate = models.ForeignKey(
        LoanRate,
        verbose_name="Tasa",
        db_column="id_rate",
        on_delete=models.PROTECT,
        related_name="loans",
        null=False,
        blank=False,
    )

    unique_code = models.CharField(
        verbose_name="Código Único",
        max_length=100,
        null=False,
        blank=True,
        default="",
    )

    loan_amount = models.DecimalField(
        verbose_name="Monto del Préstamo",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    interest_amount = models.DecimalField(
        verbose_name="Monto de Interés",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    principal_balance = models.DecimalField(
        verbose_name="Saldo de Capital",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    interest_balance = models.DecimalField(
        verbose_name="Saldo de Interés",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    term = models.PositiveIntegerField(verbose_name="Plazo", null=False, blank=False)
    installments_paid = models.PositiveIntegerField(verbose_name="Cuotas Pagadas", default=0, null=False, blank=False)

    principal_paid = models.DecimalField(
        verbose_name="Capital Pagado",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    interest_paid = models.DecimalField(
        verbose_name="Interés Pagado",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
        default=0,
    )

    start_date = models.DateField(verbose_name="Fecha de Inicio", null=False, blank=False)
    end_date = models.DateField(verbose_name="Fecha de Término", null=False, blank=False)

    is_mortgage = models.BooleanField(
        verbose_name="Hipotecario",
        default=False,
        null=False,
        blank=False,
    )

    status = models.ForeignKey(
        LoanStatus,
        verbose_name="Estado",
        db_column="id_status",
        on_delete=models.PROTECT,
        related_name="loans",
        null=False,
        blank=False,
    )

    previous_loan = models.ForeignKey(
        "self",
        verbose_name="Préstamo Anterior",
        db_column="id_previous_loan",
        on_delete=models.PROTECT,
        related_name="replacement_loans",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "loan"
        verbose_name = "Préstamo"
        verbose_name_plural = "Préstamos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Préstamo {self.id} - {self.person}"


# ============================================================
# REGISTRO CAMBIO DE TASA
class LoanRateRecord(BaseModel):
    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
        on_delete=models.PROTECT,
        related_name="rate_records",
        null=False,
        blank=False,
    )

    previous_rate = models.ForeignKey(
        LoanRate,
        verbose_name="Tasa Anterior",
        db_column="id_previous_rate",
        on_delete=models.PROTECT,
        related_name="previous_rate_records",
        null=False,
        blank=False,
    )

    new_rate = models.ForeignKey(
        LoanRate,
        verbose_name="Tasa Nueva",
        db_column="id_new_rate",
        on_delete=models.PROTECT,
        related_name="new_rate_records",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_rate_records",
        null=False,
        blank=False,
    )

    ip = models.GenericIPAddressField(verbose_name="Dirección IP", null=False, blank=False)

    class Meta:
        db_table = "loan_rate_record"
        verbose_name = "Registro de Cambio de Tasa"
        verbose_name_plural = "Registros de Cambios de Tasa"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.loan} - {self.previous_rate} → {self.new_rate}"


# ============================================================
# REGISTRO METODO DE COBRO
class LoanCollectionMethodRecord(BaseModel):
    collection_method = models.ForeignKey(
        LoanCollectionMethod,
        verbose_name="Método de Cobro",
        db_column="id_collection_method",
        on_delete=models.PROTECT,
        related_name="records",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_collection_records",
        null=True,
        blank=True,
    )

    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
        on_delete=models.PROTECT,
        related_name="collection_method_records",
        null=False,
        blank=False,
    )

    dipreca_code = models.ForeignKey(
        PersonDiprecaCode,
        verbose_name="Código DIPRECA",
        db_column="id_dipreca_code",
        on_delete=models.PROTECT,
        related_name="collection_method_records",
        null=True,
        blank=True,
    )

    ip = models.GenericIPAddressField(verbose_name="Dirección IP", null=False, blank=False)

    class Meta:
        db_table = "loan_collection_method_record"
        verbose_name = "Método de Cobro Registro"
        verbose_name_plural = "Métodos de Cobro Registros"
        ordering = ["id"]

    def __str__(self):
        return f"{self.loan} - {self.collection_method}"


# ============================================================
# AVAL DE PRESTAMO
class LoanGuarantor(BaseModel):
    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
        on_delete=models.PROTECT,
        related_name="guarantors",
        null=False,
        blank=False,
    )

    person = models.ForeignKey(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="loan_guarantees",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "loan_guarantor"
        verbose_name = "Préstamo Aval"
        verbose_name_plural = "Préstamo Avales"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["loan", "person"], name="unique_loan_guarantor"),
        ]

    def __str__(self):
        return f"{self.loan} - {self.person}"


# ============================================================
# MOVIMIENTO DE AVAL
class LoanGuarantorMovement(BaseModel):
    original_loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo Original",
        db_column="id_original_loan",
        on_delete=models.PROTECT,
        related_name="guarantor_movements",
        null=False,
        blank=False,
    )

    movement_type = models.IntegerField(verbose_name="Tipo de Movimiento", null=False, blank=False)

    observation = models.ForeignKey(
        Observation,
        verbose_name="Observación",
        db_column="id_observation",
        on_delete=models.PROTECT,
        related_name="loan_guarantor_movements",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_guarantor_movements",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "loan_guarantor_movement"
        verbose_name = "Movimiento Aval"
        verbose_name_plural = "Movimientos Aval"
        ordering = ["id"]

    def __str__(self):
        return f"{self.original_loan} - {self.movement_type}"


# ============================================================
# PRESTAMO EXTRAORDINARIO
class LoanExtraordinary(BaseModel):
    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
        on_delete=models.PROTECT,
        related_name="extraordinary_records",
        null=True,
        blank=True,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="extraordinary_loan_records",
        null=True,
        blank=True,
    )

    ip = models.GenericIPAddressField(verbose_name="Dirección IP", null=True, blank=True)

    class Meta:
        db_table = "loan_extraordinary"
        verbose_name = "Préstamo Extraordinario"
        verbose_name_plural = "Préstamos Extraordinarios"
        ordering = ["id"]

    def __str__(self):
        return f"Préstamo Extraordinario {self.id}"


# ============================================================
# DOCUMENTO DE PRESTAMO
class LoanDocument(BaseModel):
    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
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
        related_name="loan_documents",
        null=False,
        blank=False,
    )

    document_type = models.ForeignKey(
        DocumentType,
        verbose_name="Tipo de Documento",
        db_column="id_document_type",
        on_delete=models.PROTECT,
        related_name="loan_documents",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "loan_document"
        verbose_name = "Préstamo Documento"
        verbose_name_plural = "Préstamo Documentos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.loan} - {self.document}"


# ============================================================
# ESTADO DE CUOTA
class LoanInstallmentStatus(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=100, unique=True, null=False, blank=False)

    class Meta:
        db_table = "loan_installment_status"
        verbose_name = "Dividendo Estado"
        verbose_name_plural = "Dividendos Estados"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# CUOTA DE PRESTAMO
class LoanInstallment(BaseModel):
    loan = models.ForeignKey(
        Loan,
        verbose_name="Préstamo",
        db_column="id_loan",
        on_delete=models.PROTECT,
        related_name="installments",
        null=False,
        blank=False,
    )

    collection_method = models.ForeignKey(
        LoanCollectionMethod,
        verbose_name="Método de Cobro",
        db_column="id_collection_method",
        on_delete=models.PROTECT,
        related_name="installments",
        null=False,
        blank=False,
    )

    status = models.ForeignKey(
        LoanInstallmentStatus,
        verbose_name="Estado",
        db_column="id_status",
        on_delete=models.PROTECT,
        related_name="installments",
        null=False,
        blank=False,
    )

    due_date = models.DateField(verbose_name="Fecha de Vencimiento", null=False, blank=False)

    amount = models.DecimalField(
        verbose_name="Monto",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
    )

    principal = models.DecimalField(
        verbose_name="Capital",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
    )

    interest = models.DecimalField(
        verbose_name="Interés",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
    )

    installment_number = models.PositiveIntegerField(
        verbose_name="Número de Cuota",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "loan_installment"
        verbose_name = "Dividendo"
        verbose_name_plural = "Dividendos"
        ordering = ["loan", "installment_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment_number"],
                name="unique_loan_installment_number",
            ),
        ]

    def __str__(self):
        return f"{self.loan} - Cuota {self.installment_number}"
