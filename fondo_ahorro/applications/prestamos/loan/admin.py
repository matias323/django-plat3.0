from django.contrib import admin

from .models.loan import (
    Loan,
    LoanCollectionMethod,
    LoanCollectionMethodRecord,
    LoanConcept,
    LoanDocument,
    LoanExtraordinary,
    LoanGuarantor,
    LoanGuarantorMovement,
    LoanInstallment,
    LoanInstallmentStatus,
    LoanRate,
    LoanRateRecord,
    LoanStatus,
    LoanType,
    LoanTypeConcept,
)

from .models.payment import (
    LoanDocumentNumber,
    LoanDocumentNumberType,
    LoanPayment,
    LoanPaymentContribution,
    LoanPaymentDeposit,
    LoanPaymentDocument,
    LoanPaymentExternal,
    LoanPaymentExternalDocument,
    LoanPaymentExternalMethod,
    LoanPaymentReversal,
    LoanPaymentStatus,
    LoanPaymentType,
)


# ============================================================
# ADMIN BASE
class LoanBaseAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25


# ============================================================
# TIPO DE PRESTAMO
@admin.register(LoanType)
class LoanTypeAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# CONCEPTO DE PRESTAMO
@admin.register(LoanConcept)
class LoanConceptAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# TIPO DE PRESTAMO CONCEPTO
@admin.register(LoanTypeConcept)
class LoanTypeConceptAdmin(LoanBaseAdmin):
    list_display = ("id", "loan_type", "concept", "is_active")
    list_display_links = ("id", "loan_type", "concept")
    list_filter = ("loan_type", "concept", "is_active")
    search_fields = ("loan_type__name", "concept__name")
    list_select_related = ("loan_type", "concept")
    ordering = ("id",)


# ============================================================
# TASA DE PRESTAMO
@admin.register(LoanRate)
class LoanRateAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "rate", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# ESTADO DE PRESTAMO
@admin.register(LoanStatus)
class LoanStatusAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# METODO DE COBRO
@admin.register(LoanCollectionMethod)
class LoanCollectionMethodAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# PRESTAMO
@admin.register(Loan)
class LoanAdmin(LoanBaseAdmin):
    list_display = (
        "id",
        "unique_code",
        "person",
        "loan_type",
        "type_concept",
        "loan_amount",
        "principal_balance",
        "term",
        "installments_paid",
        "collection_method",
        "status",
        "start_date",
        "end_date",
        "is_active",
    )

    list_display_links = ("id", "unique_code", "person")

    list_filter = (
        "loan_type",
        "type_concept",
        "collection_method",
        "rate",
        "status",
        "start_date",
        "end_date",
        "is_active",
    )

    search_fields = ("unique_code",)
    list_select_related = ("person", "loan_type", "type_concept", "collection_method", "rate", "status")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"


# ============================================================
# REGISTRO METODO DE COBRO
@admin.register(LoanCollectionMethodRecord)
class LoanCollectionMethodRecordAdmin(LoanBaseAdmin):
    list_display = ("id", "loan", "collection_method", "dipreca_code", "document", "ip", "created_at", "is_active")
    list_display_links = ("id", "loan")
    list_filter = ("collection_method", "is_active")
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "collection_method", "dipreca_code", "document")
    ordering = ("-created_at",)


# ============================================================
# AVAL DE PRESTAMO
@admin.register(LoanGuarantor)
class LoanGuarantorAdmin(LoanBaseAdmin):
    list_display = ("id", "loan", "person", "created_at", "is_active")
    list_display_links = ("id", "loan", "person")
    list_filter = ("is_active",)
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "person")
    ordering = ("-created_at",)


# ============================================================
# MOVIMIENTO DE AVAL
@admin.register(LoanGuarantorMovement)
class LoanGuarantorMovementAdmin(LoanBaseAdmin):
    list_display = ("id", "original_loan", "movement_type", "observation", "document", "created_at", "is_active")
    list_display_links = ("id", "original_loan")
    list_filter = ("movement_type", "is_active")
    search_fields = ("original_loan__unique_code",)
    list_select_related = ("original_loan", "observation", "document")
    ordering = ("-created_at",)


# ============================================================
# PRESTAMO EXTRAORDINARIO
@admin.register(LoanExtraordinary)
class LoanExtraordinaryAdmin(LoanBaseAdmin):
    list_display = ("id", "loan", "document", "ip", "created_at", "is_active")
    list_display_links = ("id", "loan")
    list_filter = ("is_active",)
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "document")
    ordering = ("-created_at",)


# ============================================================
# DOCUMENTO DE PRESTAMO
@admin.register(LoanDocument)
class LoanDocumentAdmin(LoanBaseAdmin):
    list_display = ("id", "loan", "document_type", "document", "created_at", "is_active")
    list_display_links = ("id", "loan")
    list_filter = ("document_type", "is_active")
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "document", "document_type")
    ordering = ("-created_at",)


# ============================================================
# ESTADO DE CUOTA
@admin.register(LoanInstallmentStatus)
class LoanInstallmentStatusAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# CUOTA DE PRESTAMO
@admin.register(LoanInstallment)
class LoanInstallmentAdmin(LoanBaseAdmin):
    list_display = (
        "id",
        "loan",
        "installment_number",
        "due_date",
        "amount",
        "principal",
        "interest",
        "collection_method",
        "status",
        "is_active",
    )

    list_display_links = ("id", "loan", "installment_number")
    list_filter = ("collection_method", "status", "due_date", "is_active")
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "collection_method", "status")
    ordering = ("loan", "installment_number")


# ============================================================
# TIPO DE PAGO
@admin.register(LoanPaymentType)
class LoanPaymentTypeAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# ESTADO DE PAGO
@admin.register(LoanPaymentStatus)
class LoanPaymentStatusAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# PAGO DE PRESTAMO
@admin.register(LoanPayment)
class LoanPaymentAdmin(LoanBaseAdmin):
    list_display = (
        "id",
        "loan",
        "installment",
        "payment_type",
        "amount",
        "previous_balance",
        "previous_installment",
        "status",
        "status_changed_at",
        "ip",
        "is_active",
    )

    list_display_links = ("id", "loan")
    list_filter = ("payment_type", "status", "status_changed_at", "is_active")
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "installment", "payment_type", "status")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"


# ============================================================
# REVERSA DE PAGO
@admin.register(LoanPaymentReversal)
class LoanPaymentReversalAdmin(LoanBaseAdmin):
    list_display = ("id", "payment", "reason", "document", "ip", "created_at", "is_active")
    list_display_links = ("id", "payment")
    list_filter = ("is_active",)
    search_fields = ("reason", "payment__loan__unique_code")
    list_select_related = ("payment", "document")
    ordering = ("-created_at",)


# ============================================================
# APORTE EN PAGO
@admin.register(LoanPaymentContribution)
class LoanPaymentContributionAdmin(LoanBaseAdmin):
    list_display = (
        "id",
        "payment",
        "contribution_type",
        "contribution_amount",
        "previous_contribution_balance",
        "created_at",
        "is_active",
    )

    list_display_links = ("id", "payment")
    list_filter = ("contribution_type", "is_active")
    search_fields = ("payment__loan__unique_code",)
    list_select_related = ("payment", "contribution_type")
    ordering = ("-created_at",)


# ============================================================
# DOCUMENTO DE PAGO
@admin.register(LoanPaymentDocument)
class LoanPaymentDocumentAdmin(LoanBaseAdmin):
    list_display = ("id", "payment", "document", "created_at", "is_active")
    list_display_links = ("id", "payment")
    list_filter = ("is_active",)
    search_fields = ("payment__loan__unique_code",)
    list_select_related = ("payment", "document")
    ordering = ("-created_at",)


# ============================================================
# DEPOSITO DE PAGO
@admin.register(LoanPaymentDeposit)
class LoanPaymentDepositAdmin(LoanBaseAdmin):
    list_display = ("id", "payment", "amount", "document", "created_at", "is_active")
    list_display_links = ("id", "payment")
    list_filter = ("is_active",)
    search_fields = ("payment__loan__unique_code",)
    list_select_related = ("payment", "document")
    ordering = ("-created_at",)


# ============================================================
# METODO DE PAGO EXTRASISTEMA
@admin.register(LoanPaymentExternalMethod)
class LoanPaymentExternalMethodAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# PAGO EXTRASISTEMA
@admin.register(LoanPaymentExternal)
class LoanPaymentExternalAdmin(LoanBaseAdmin):
    list_display = ("id", "payment", "method", "contribution_type", "amount", "created_at", "is_active")
    list_display_links = ("id", "payment")
    list_filter = ("method", "contribution_type", "is_active")
    search_fields = ("payment__loan__unique_code",)
    list_select_related = ("payment", "method", "contribution_type")
    ordering = ("-created_at",)


# ============================================================
# DOCUMENTO DE PAGO EXTRASISTEMA
@admin.register(LoanPaymentExternalDocument)
class LoanPaymentExternalDocumentAdmin(LoanBaseAdmin):
    list_display = ("id", "external_payment", "document", "created_at", "is_active")
    list_display_links = ("id", "external_payment")
    list_filter = ("is_active",)
    search_fields = ("external_payment__payment__loan__unique_code",)
    list_select_related = ("external_payment", "document")
    ordering = ("-created_at",)


# ============================================================
# TIPO DE NUMERO DE DOCUMENTO
@admin.register(LoanDocumentNumberType)
class LoanDocumentNumberTypeAdmin(LoanBaseAdmin):
    list_display = ("id", "name", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("id",)


# ============================================================
# NUMERO DE DOCUMENTO
@admin.register(LoanDocumentNumber)
class LoanDocumentNumberAdmin(LoanBaseAdmin):
    list_display = ("id", "document", "number_type", "number", "created_at", "is_active")
    list_display_links = ("id", "document")
    list_filter = ("number_type", "is_active")
    search_fields = ("=number",)
    list_select_related = ("document", "number_type")
    ordering = ("-created_at",)


# ============================================================
# REGISTRO CAMBIO DE TASA
@admin.register(LoanRateRecord)
class LoanRateRecordAdmin(LoanBaseAdmin):
    list_display = (
        "id",
        "loan",
        "previous_rate",
        "new_rate",
        "document",
        "ip",
        "created_at",
        "is_active",
    )

    list_display_links = ("id", "loan")
    list_filter = ("previous_rate", "new_rate", "is_active")
    search_fields = ("loan__unique_code",)
    list_select_related = ("loan", "previous_rate", "new_rate", "document")
    ordering = ("-created_at",)