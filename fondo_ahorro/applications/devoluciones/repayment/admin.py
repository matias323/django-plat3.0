
from django.contrib import admin

from .models import (
    DevoConsejo,
    DevoMetodoPago,
    DevoSolicitud,
    DevoSolicitudAporte,
    DevoSolicitudConcepto,
    DevoSolicitudDetalle,
    DevoSolicitudEstado,
    DevoSolicitudMotivo,
    DevoSolicitudTipo,
    DevoSolicitudTipoConcepto,
    DevoTipoConcepto,
)


# ============================================================
# CONSEJOS
# ============================================================
@admin.register(DevoConsejo)
class DevoConsejoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha_consejo", "estado", "fecha_creacion", "is_active")
    search_fields = ("id",)
    list_filter = ("estado", "is_active", "fecha_consejo")
    ordering = ("-fecha_consejo",)


# ============================================================
# MOTIVOS DE DEVOLUCIÓN
# ============================================================
@admin.register(DevoSolicitudMotivo)
class DevoSolicitudMotivoAdmin(admin.ModelAdmin):
    list_display = ("id", "descripcion", "is_active")
    search_fields = ("descripcion",)
    list_filter = ("is_active",)
    ordering = ("id",)


# ============================================================
# CONCEPTOS DE DEVOLUCIÓN
# ============================================================
@admin.register(DevoSolicitudConcepto)
class DevoSolicitudConceptoAdmin(admin.ModelAdmin):
    list_display = ("id", "descripcion", "is_active")
    search_fields = ("descripcion",)
    list_filter = ("is_active",)
    ordering = ("id",)


# ============================================================
# TIPOS DE DEVOLUCIÓN
# ============================================================
@admin.register(DevoSolicitudTipo)
class DevoSolicitudTipoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "is_active")
    search_fields = ("nombre",)
    list_filter = ("is_active",)
    ordering = ("id",)


# ============================================================
# ESTADOS DE DEVOLUCIÓN
# ============================================================
@admin.register(DevoSolicitudEstado)
class DevoSolicitudEstadoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "is_active")
    search_fields = ("nombre",)
    list_filter = ("is_active",)
    ordering = ("id",)


# ============================================================
# SOLICITUDES DE DEVOLUCIÓN
# ============================================================
@admin.register(DevoSolicitud)
class DevoSolicitudAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitud",
        "motivo",
        "estado",
        "grado",
        "consejo",
        "fecha_retiro",
        "fecha_aprobacion",
        "fecha_pago",
        "is_active",
    )

    search_fields = (
        "=id",
        "=solicitud__id",
        "motivo__descripcion",
        "estado__nombre",
    )

    list_filter = (
        "estado",
        "motivo",
        "grado",
        "consejo",
        "is_active",
        "fecha_retiro",
        "fecha_aprobacion",
        "fecha_pago",
    )

    autocomplete_fields = (
        "motivo",
        "estado",
        "consejo",
    )

    list_select_related = (
        "solicitud",
        "motivo",
        "estado",
        "grado",
        "consejo",
    )

    ordering = ("-id",)
    date_hierarchy = "created_at"


# ============================================================
# APORTES DE SOLICITUDES
# ============================================================
@admin.register(DevoSolicitudAporte)
class DevoSolicitudAporteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitud_devolucion",
        "aporte_tipo",
        "monto",
        "is_active",
    )

    search_fields = (
        "=id",
        "=solicitud_devolucion__id",
        "aporte_tipo__description",
    )

    list_filter = (
        "aporte_tipo",
        "is_active",
    )

    autocomplete_fields = (
        "solicitud_devolucion",
    )

    list_select_related = (
        "solicitud_devolucion",
        "aporte_tipo",
    )



# ============================================================
# DETALLE DE SOLICITUDES
# ============================================================
@admin.register(DevoSolicitudDetalle)
class DevoSolicitudDetalleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitud_devolucion",
        "persona",
        "metodo_pago",
        "persona_banco",
        "is_active",
    )

    search_fields = (
        "=id",
        "=solicitud_devolucion__id",
        "persona__first_name",
        "persona__second_name",
        "persona__last_name_1",
        "persona__last_name_2",
        "metodo_pago__tipo",
        "persona_banco__n_cuenta",
    )

    list_filter = (
        "metodo_pago",
        "is_active",
    )

    autocomplete_fields = (
        "solicitud_devolucion",
        "metodo_pago",
    )

    list_select_related = (
        "solicitud_devolucion",
        "persona",
        "metodo_pago",
        "persona_banco",
    )



# ============================================================
# RELACIÓN TIPO - CONCEPTO
# ============================================================
@admin.register(DevoTipoConcepto)
class DevoTipoConceptoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitud_tipo",
        "solicitud_concepto",
        "is_active",
    )

    search_fields = (
        "=id",
        "solicitud_tipo__nombre",
        "solicitud_concepto__descripcion",
    )

    list_filter = (
        "solicitud_tipo",
        "is_active",
    )

    autocomplete_fields = (
        "solicitud_tipo",
        "solicitud_concepto",
    )

    list_select_related = (
        "solicitud_tipo",
        "solicitud_concepto",
    )


# ============================================================
# CONCEPTOS ASOCIADOS A UNA SOLICITUD
# ============================================================
@admin.register(DevoSolicitudTipoConcepto)
class DevoSolicitudTipoConceptoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitud_devolucion",
        "tipo_concepto",
        "is_active",
    )

    search_fields = (
        "=id",
        "=solicitud_devolucion__id",
        "tipo_concepto__solicitud_tipo__nombre",
        "tipo_concepto__solicitud_concepto__descripcion",
    )

    list_filter = (
        "tipo_concepto__solicitud_tipo",
        "is_active",
    )

    autocomplete_fields = (
        "solicitud_devolucion",
        "tipo_concepto",
    )

    list_select_related = (
        "solicitud_devolucion",
        "tipo_concepto",
    )


# ============================================================
# MÉTODOS DE PAGO
# ============================================================
@admin.register(DevoMetodoPago)
class DevoMetodoPagoAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "is_active")
    search_fields = ("tipo",)
    list_filter = ("is_active",)
    ordering = ("tipo",)
