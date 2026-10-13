from django.urls import path
from .views import (DepositoView, DepositoPartnerSearch)




app_name = "depositos" 
urlpatterns = [
    #vistas
    path("", DepositoView.as_view(), name="incremento_aporte"),
    path("busqueda-partner/", DepositoPartnerSearch.as_view(), name="depositos_busqueda_partner"),

    
]