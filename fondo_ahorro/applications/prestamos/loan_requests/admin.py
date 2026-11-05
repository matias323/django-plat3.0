from django.contrib import admin

from .models import (
    RequestLoan,
    RequestLoanDocument,
    RequestLoanDocumentRequirement,
    RequestLoanObservation,
    RequestLoanRequiredDocument,
    RequestLoanState,
)


@admin.register(RequestLoan)
class RequestLoanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee",
        "request_date",
        "request_status",
        "is_active",
    )

    search_fields = (
        "employee__code",
        "employee__person__rut",
        "employee__person__first_name",
        "employee__person__second_name",
        "employee__person__last_name_1",
        "employee__person__last_name_2",
        "description",
    )

    list_filter = (
        "request__status",
        "request_date",
        "is_active",
    )

    raw_id_fields = ("employee",)

    @admin.display(description="Estado")
    def request_status(self, obj):
        return obj.request.status.status_type


@admin.register(RequestLoanDocumentRequirement)
class RequestLoanDocumentRequirementAdmin(admin.ModelAdmin):
    list_display = ("id","document_type","is_active",)
    search_fields = ("document_type__name",)
    list_filter = ("is_active",)


@admin.register(RequestLoanRequiredDocument)
class RequestLoanRequiredDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "request_loan", "document_type", "is_active")
    search_fields = ("request_loan__id", "document_type__name")
    list_filter = ("is_active",)


@admin.register(RequestLoanDocument)
class RequestLoanDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "required_document", "document", "status", "validated_by", "validated_at")
    list_filter = ("status", "is_active")
    search_fields = (
        "document__document_name",
        "required_document__document_type__name",
        "required_document__request_loan__employee__code",
    )


@admin.register(RequestLoanObservation)
class RequestLoanObservationAdmin(admin.ModelAdmin):
    list_display = ("id", "request_loan", "action", "observation", "created_at")
    list_filter = ("action", "is_active")
    search_fields = (
        "request_loan__employee__code",
        "observation__comment",
    )

@admin.register(RequestLoanState)
class RequestLoanStateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sequence", "is_approval_state", "is_paid_state", "is_active")
    search_fields = ("name", "code")
    ordering = ("sequence", "id")
    filter_horizontal = ("allowed_next_states",)

    def log_addition(self, request, object, message):
        """Evita que Django Admin intente serializar el objeto al crearlo."""
        pass

    def log_change(self, request, object, message):
        """Evita que Django Admin intente serializar el objeto al modificarlo."""
        pass