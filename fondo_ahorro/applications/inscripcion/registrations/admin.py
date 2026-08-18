from django.contrib import admin

from .models import (
    Registration,
    RegistrationType,
    RegistrationDocument,
    RegistrationDocumentStatus,
    RegistrationObservation,
)


# ============================================================
# TIPO DE INSCRIPCIÓN
@admin.register(RegistrationType)
class RegistrationTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "state")
    list_display_links = ("id", "type", "state")
    list_filter = ("state",)
    search_fields = ("type",)
    ordering = ("id",)


# ============================================================
# SOLICITUD DE INSCRIPCIÓN
@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "person",
        "registration_type",
        "contributes_a2",
        "user",
        "user_ip",
    )

    list_display_links = (
        "id",
        "request",
        "person",
    )

    list_filter = (
        "registration_type",
        "request__status",
    )

    search_fields = (
        "person__rut",
        "person__first_name",
        "person__second_name",
        "person__last_name_1",
        "person__last_name_2",
        "registration_type__type",
    )

    list_select_related = (
        "request",
        "request__status",
        "person",
        "registration_type",
        "user",
    )

    ordering = ("-id",)
    list_per_page = 25


# ============================================================
# ESTADO DE DOCUMENTO
@admin.register(RegistrationDocumentStatus)
class RegistrationDocumentStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "status_type", "state")
    list_display_links = ("id", "status_type", "state")
    list_filter = ("state",)
    search_fields = ("status_type",)
    ordering = ("id",)


# ============================================================
# DOCUMENTOS DE LA SOLICITUD
@admin.register(RegistrationDocument)
class RegistrationDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "registration",
        "document",
        "status",
    )

    list_display_links = (
        "id",
        "registration",
    )

    list_filter = (
        "status",
        "document__type_document",
    )

    search_fields = (
        "document__document_name",
        "registration__person__rut",
        "registration__person__first_name",
        "registration__person__last_name_1",
    )

    list_select_related = (
        "registration",
        "registration__person",
        "document",
        "document__type_document",
        "status",
    )

    ordering = ("-id",)
    list_per_page = 25


# ============================================================
# OBSERVACIONES
@admin.register(RegistrationObservation)
class RegistrationObservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "registration",
        "observation",
        "state",
    )

    list_display_links = (
        "id",
        "registration",
    )

    list_filter = (
        "state",
        "observation__date",
    )

    search_fields = (
        "observation__comment",
        "registration__person__rut",
        "registration__person__first_name",
        "registration__person__last_name_1",
    )

    list_select_related = (
        "registration",
        "registration__person",
        "observation",
        "observation__user",
    )

    ordering = ("-id",)
    list_per_page = 25