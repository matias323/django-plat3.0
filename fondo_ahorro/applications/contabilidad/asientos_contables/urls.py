from django.urls import path
from .views import AsientosContablesView


app_name = "asientos_contables" 
urlpatterns = [
    path("", AsientosContablesView.as_view(), name="crear_asiento"),
    # path("editar/<int:pk>/", EditarCuentaApiView.as_view(), name="editar_cuenta"),
    # path("exportar/", ExportarPlanCuentasView.as_view(), name="exportar_plan_cuentas"),
    # path("activar/<int:pk>/", ActivarCuentaView.as_view(), name="activar_cuenta"),
    # path("<pk:int>", CuentaView.as_view(), name="detalle"),


]