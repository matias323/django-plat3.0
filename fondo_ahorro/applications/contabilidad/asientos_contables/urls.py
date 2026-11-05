from django.urls import path
from .views import (
    AsientosContablesView, 
    AsientoPersonaSearchView, 
    AsientoContableCreate, 
    AsientosContablesPeriodoView, 
    AsientosContablesPeriodoAllView,
    AsientoContableUpdateView,
    AsientoContableAnularView,
    AsientoContableQuitarNuloView,
    AsientoContableCheckView,
    AsientoContableValidateView,
    AsientoContablePDFView,
    AsientosContablesBusquedaView,
    AsientosContablesBuscarView,
    LibroDiarioView,
    LibroDiarioPDFView,
    LibroMayorView,
    LibroMayorData,
    LibroMayorExcel,
    LibroDiarioExcel,
    LibroMayorPDF)


app_name = "asientos_contables" 
urlpatterns = [
    #vistas
    path("", AsientosContablesView.as_view(), name="asiento"),
    path("asiento_periodo/", AsientosContablesPeriodoView.as_view(), name="asiento_periodo"),
    path("busqueda/", AsientosContablesBusquedaView.as_view(), name="asiento_busqueda"),
    path("libro_diario/", LibroDiarioView.as_view(), name="libro_diario"),
    path("libro_mayor/", LibroMayorView.as_view(), name="libro_mayor"),
    
    #pdf
    path("pdf/<int:pk>/", AsientoContablePDFView.as_view(), name="asiento_pdf"),
    path("libro_diario/pdf/", LibroDiarioPDFView.as_view(), name="libro_diario_pdf"),
    path("libro_mayor/pdf/", LibroMayorPDF.as_view(), name="libro_mayor_pdf"),
    
    #excel
    path("libro_diario/excel/", LibroDiarioExcel.as_view(), name="libro_diario_excel"),
    path("libro_mayor/excel/", LibroMayorExcel.as_view(), name="libro_mayor_excel"),
    
    #peticiones
    path("asiento_periodo/all/", AsientosContablesPeriodoAllView.as_view(), name="asiento_periodo_all"),
    path("update/<int:pk>/", AsientoContableUpdateView.as_view(), name="asiento_update"),
    path("anular/<int:pk>/", AsientoContableAnularView.as_view(), name="asiento_anular"),
    path("quitar_nulo_asiento/<int:pk>/", AsientoContableQuitarNuloView.as_view(), name="asiento_quitar_nulo"),
    path("check_edit/", AsientoContableCheckView.as_view(), name="asiento_check_edit"),
    path("uncheck_edit/<int:pk>/", AsientoContableCheckView.as_view(), name="asiento_uncheck_edit"),
    path("validate/<int:pk>/", AsientoContableValidateView.as_view(), name="asiento_validate"),
    path("busqueda/buscar/", AsientosContablesBuscarView.as_view(), name="asiento_busqueda_buscar"),
    path("buscar_persona/", AsientoPersonaSearchView.as_view(), name="buscar_persona"),
    path("contabilizar/", AsientoContableCreate.as_view(), name="contabilizar_asiento"),
    path("libro_mayor/data/", LibroMayorData.as_view(), name="libro_mayor_data"),
]