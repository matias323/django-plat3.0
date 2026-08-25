"""
URL configuration for fondo_ahorro project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from .views import PeriodoContableTemplate, PeriodoContableView


app_name = "periodo_contable" 

urlpatterns = [
    path("", PeriodoContableTemplate.as_view(), name="periodo"),
    path("all/", PeriodoContableView.as_view(), name="all_periodos"),
    path("nuevo-periodo/", PeriodoContableView.as_view(), name="nuevo_periodo"),
    # path("editar/<int:pk>/", EditarCuentaApiView.as_view(), name="editar_cuenta"),
    # path("exportar/", ExportarPlanCuentasView.as_view(), name="exportar_plan_cuentas"),
    # path("activar/<int:pk>/", ActivarCuentaView.as_view(), name="activar_cuenta"),
    # path("<pk:int>", CuentaView.as_view(), name="detalle"),


]