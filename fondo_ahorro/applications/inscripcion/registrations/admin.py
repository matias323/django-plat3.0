from django.contrib import admin

from .models import (
    Registration,
    RegistrationType,
    RegistrationDocument,
    RegistrationDocumentStatus,
    RegistrationObservation,
)


class BaseAuditAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at", "user_create", "user_update")

    def save_model(self, request, obj, form, change):
        obj.save(user=request.user)


@admin.register(RegistrationType)
class RegistrationTypeAdmin(BaseAuditAdmin):
    list_display = ("id", "type", "is_active", "created_at", "updated_at")
    list_display_links = ("id", "type")
    list_filter = ("is_active",)
    search_fields = ("type",)
    ordering = ("id",)


@admin.register(Registration)
class RegistrationAdmin(BaseAuditAdmin):
    list_display = (
        "id",
        "request",
        "person",
        "registration_type",
        "contributes_a2",
        "user_ip",
        "is_active",
        "created_at",
        "user_create",
    )

    list_display_links = ("id", "request", "person")

    list_filter = (
        "is_active",
        "registration_type",
        "request__status",
        "created_at",
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
        "user_create",
    )

    ordering = ("-created_at",)
    list_per_page = 25


@admin.register(RegistrationDocumentStatus)
class RegistrationDocumentStatusAdmin(BaseAuditAdmin):
    list_display = ("id", "status_type", "is_active", "created_at", "updated_at")
    list_display_links = ("id", "status_type")
    list_filter = ("is_active",)
    search_fields = ("status_type",)
    ordering = ("id",)


@admin.register(RegistrationDocument)
class RegistrationDocumentAdmin(BaseAuditAdmin):
    list_display = (
        "id",
        "registration",
        "document",
        "status",
        "is_active",
        "created_at",
        "user_create",
    )

    list_display_links = ("id", "registration")

    list_filter = (
        "is_active",
        "status",
        "document__type_document",
        "created_at",
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
        "user_create",
    )

    ordering = ("-created_at",)
    list_per_page = 25


@admin.register(RegistrationObservation)
class RegistrationObservationAdmin(BaseAuditAdmin):
    list_display = (
        "id",
        "registration",
        "observation",
        "is_active",
        "created_at",
        "user_create",
    )

    list_display_links = ("id", "registration")

    list_filter = (
        "is_active",
        "created_at",
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
        "user_create",
    )

    ordering = ("-created_at",)
    list_per_page = 25
