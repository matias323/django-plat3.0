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
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    #apps-urls
    path('', include('core.urls'),name="core"),
    path('devolucion/solicitud/', include('applications.devoluciones.dev_solicitud.urls'),name="dev_solicitud"),
    path('devolucion/consejo/', include('applications.devoluciones.dev_consejo.urls'),name="dev_consejo"),
    path('contabilidad/plan_cuentas/', include('applications.contabilidad.plan_cuentas.urls'),name="plan_cuentas"),
    path('contabilidad/periodo_contable/', include('applications.contabilidad.periodo_contable.urls'),name="periodo_contable"),

    path("registrations/",include("applications.inscripcion.registrations.urls")),
]
