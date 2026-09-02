from django.urls import path
from .views import AsientosContablesView, AsientoContableEncabezadoView, AsientoMovimientoCreateView, AsientoPersonaSearchView


app_name = "asientos_contables" 
urlpatterns = [
    path("", AsientosContablesView.as_view(), name="asiento_form"),
    path("nuevo/", AsientoContableEncabezadoView.as_view(), name="crear_asiento_encabezado"),
    path("nuevo_movimiento/<int:pk>/", AsientoMovimientoCreateView.as_view(), name="nuevo_movimiento"),
    path("buscar_persona/", AsientoPersonaSearchView.as_view(), name="buscar_persona"),
    # path("exportar/", ExportarPlanCuentasView.as_view(), name="exportar_plan_cuentas"),
    # path("activar/<int:pk>/", ActivarCuentaView.as_view(), name="activar_cuenta"),
    # path("<pk:int>", CuentaView.as_view(), name="detalle"),


]