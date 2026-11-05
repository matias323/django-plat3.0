from django.urls import path
from .views import (DepositoView, 
                    DepositoPartnerSearch, 
                    DepositoIncrementoAporte, 
                    DepositoIncrementoAportePDF,
                    DepositoSearchView, 
                    DepositosBusqueda,
                    DepositoAppComprobantePDF,
                    DepositoCartola,
                    CartolaMovimientos)




app_name = "depositos" 
urlpatterns = [
    #vistas
    path("incremento-aporte/", DepositoView.as_view(), name="incremento_aporte"),
    path("", DepositoSearchView.as_view(), name="depositos_busqueda"),
    path("cartola/", DepositoCartola.as_view(), name="depositos_cartola"),
    
    #peticiones
    path("busqueda-partner/", DepositoPartnerSearch.as_view(), name="depositos_busqueda_partner"),
    path("incremento/", DepositoIncrementoAporte.as_view(), name="depositos_incremento_aporte"),
    path("busqueda/", DepositosBusqueda.as_view(), name="depositos_buscar"),
    path("cartola/movimientos/", CartolaMovimientos.as_view(), name="depositos_cartola_movimientos"),
    
    
    #pdf
    path("comprobante-incremento/pdf/<int:pk>/", DepositoIncrementoAportePDF.as_view(), name="depositos_incremento_aporte_pdf"),
    path("comprobante-app/pdf/<int:pk>/", DepositoAppComprobantePDF.as_view(), name="depositos_app_comprobante_pdf"),

    
]