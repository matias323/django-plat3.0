from django.conf import settings
from django.db import models

from core.models.base import BaseModel
from core.models.document import Document, DocumentType
from core.models.employee import Employee
from core.models.observation import Observation
from core.models.request import Request
from applications.prestamos.loan.models.loan import LoanType, LoanTypeConcept, LoanRate


# ============================================================
# SOLICITUD DE PRÉSTAMO
# ============================================================
class RequestLoan(BaseModel):
    request = models.OneToOneField(
        Request,
        verbose_name="Solicitud",
        db_column="id_request",
        on_delete=models.PROTECT,
        related_name="loan_request",
    )

    employee = models.ForeignKey(
        Employee,
        verbose_name="Funcionario",
        db_column="id_employee",
        on_delete=models.PROTECT,
        related_name="loan_requests",
    )

    loan_type = models.ForeignKey(
        LoanType,
        verbose_name="Tipo de préstamo",
        db_column="id_loan_type",
        on_delete=models.PROTECT,
        related_name="loan_requests",
    )

    type_concept = models.ForeignKey(
        LoanTypeConcept,
        verbose_name="Concepto de préstamo",
        db_column="id_type_concept",
        on_delete=models.PROTECT,
        related_name="loan_requests",
    )

    loan_amount = models.DecimalField(
        verbose_name="Monto solicitado",
        max_digits=15,
        decimal_places=2,
    )

    term = models.PositiveIntegerField(
        verbose_name="Plazo",
    )

    request_date = models.DateField(
        verbose_name="Fecha de solicitud",
    )

    def can_be_approved(self):
        required_documents = (
            self.required_documents
            .filter(is_active=True)
            .prefetch_related("documents")
        )

        if not required_documents.exists():
            return False

        for required in required_documents:
            latest = (
                required.documents
                .filter(is_active=True)
                .order_by("-id")
                .first()
            )

            if not latest:
                return False

            if latest.status != RequestLoanDocument.Status.APPROVED:
                return False

        return True

    class Meta:
        db_table = "request_loan"
        verbose_name = "Solicitud de préstamo"
        verbose_name_plural = "Solicitudes de préstamos"


# ============================================================
# CONFIGURACIÓN DE DOCUMENTOS REQUERIDOS
# id / id_document_type / active
# ============================================================
class RequestLoanDocumentRequirement(BaseModel):
    document_type = models.ForeignKey(
        DocumentType,
        verbose_name="Tipo de documento",
        db_column="id_document_type",
        on_delete=models.PROTECT,
        related_name="loan_request_requirements",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "request_loan_document_requirement"
        verbose_name = "Documento requerido para solicitud de préstamo"
        verbose_name_plural = "Documentos requeridos para solicitudes de préstamo"
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=["document_type"],
                name="unique_request_loan_document_requirement",
            ),
        ]

    def __str__(self):
        return str(self.document_type)


# ============================================================
# DOCUMENTOS EXIGIDOS A UNA SOLICITUD ESPECÍFICA
# Copia histórica de los requisitos activos al crear la solicitud.
# ============================================================
class RequestLoanRequiredDocument(BaseModel):
    request_loan = models.ForeignKey(
        RequestLoan,
        verbose_name="Solicitud de préstamo",
        db_column="id_request_loan",
        on_delete=models.CASCADE,
        related_name="required_documents",
        null=False,
        blank=False,
    )

    document_type = models.ForeignKey(
        DocumentType,
        verbose_name="Tipo de documento",
        db_column="id_document_type",
        on_delete=models.PROTECT,
        related_name="loan_request_required_documents",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "request_loan_required_document"
        verbose_name = "Documento requerido de solicitud de préstamo"
        verbose_name_plural = "Documentos requeridos de solicitudes de préstamos"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["request_loan", "document_type"],
                name="unique_request_loan_required_document",
            ),
        ]

    def __str__(self):
        return f"{self.request_loan} - {self.document_type}"

    @property
    def latest_document(self):
        return self.documents.select_related(
            "document",
            "document__type_document",
            "validated_by",
        ).order_by("-id").first()


# ============================================================
# DOCUMENTOS ADJUNTOS
# Se conservan todas las versiones para mantener historial.
# ============================================================
class RequestLoanDocument(BaseModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        APPROVED = "APPROVED", "Aprobado"
        REJECTED = "REJECTED", "Rechazado"

    required_document = models.ForeignKey(
        RequestLoanRequiredDocument,
        verbose_name="Documento requerido",
        db_column="id_required_document",
        on_delete=models.CASCADE,
        related_name="documents",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Documento",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_request_documents",
        null=False,
        blank=False,
    )

    status = models.CharField(
        verbose_name="Estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        null=False,
        blank=False,
    )

    rejection_comment = models.TextField(
        verbose_name="Motivo del rechazo",
        null=True,
        blank=True,
    )

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Validado por",
        db_column="id_validated_by",
        on_delete=models.PROTECT,
        related_name="validated_loan_request_documents",
        null=True,
        blank=True,
    )

    validated_at = models.DateTimeField(
        verbose_name="Fecha de validación",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "request_loan_document"
        verbose_name = "Documento de solicitud de préstamo"
        verbose_name_plural = "Documentos de solicitudes de préstamos"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.required_document} - {self.get_status_display()}"


# ============================================================
# OBSERVACIONES DE SOLICITUD DE PRÉSTAMO
# ============================================================
class RequestLoanObservation(BaseModel):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Solicitud creada"
        DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED", "Documento adjuntado"
        DOCUMENT_APPROVED = "DOCUMENT_APPROVED", "Documento aprobado"
        DOCUMENT_REJECTED = "DOCUMENT_REJECTED", "Documento rechazado"
        REQUEST_APPROVED = "REQUEST_APPROVED", "Solicitud aprobada"
        REQUEST_REJECTED = "REQUEST_REJECTED", "Solicitud rechazada"
        COMMENT = "COMMENT", "Observación"

    request_loan = models.ForeignKey(
        RequestLoan,
        verbose_name="Solicitud de préstamo",
        db_column="id_request_loan",
        on_delete=models.CASCADE,
        related_name="observations",
        null=False,
        blank=False,
    )

    observation = models.ForeignKey(
        Observation,
        verbose_name="Observación",
        db_column="id_observation",
        on_delete=models.PROTECT,
        related_name="loan_request_observations",
        null=False,
        blank=False,
    )

    action = models.CharField(
        verbose_name="Acción",
        max_length=30,
        choices=Action.choices,
        default=Action.COMMENT,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "request_loan_observation"
        verbose_name = "Observación de solicitud de préstamo"
        verbose_name_plural = "Observaciones de solicitudes de préstamos"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.request_loan} - {self.get_action_display()}"
