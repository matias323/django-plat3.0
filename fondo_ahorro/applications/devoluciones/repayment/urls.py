from django.urls import path
from . import views

app_name = 'devolucion'
urlpatterns = [
    path('', views.lista, name='lista'),
    path('crear/', views.crear_solicitud, name='crear_solicitud'),
    path('regiones/<int:region_id>/comunas/', views.comunas_region, name='comunas_region'),
    path('bancos/<int:banco_id>/cuentas/', views.cuentas_banco, name='cuentas_banco'),
    path('datatable/', views.datatable, name='datatable'),
    path('<int:pk>/detalle/', views.detalle_solicitud, name='detalle_solicitud'),
    path('<int:pk>/estado/', views.cambiar_estado_solicitud, name='cambiar_estado_solicitud'),
    path('modal/crear/', views.modal_crear, name='modal_crear'),
    path('funcionarios/buscar/', views.buscar_funcionarios, name='buscar_funcionarios'),
    path('funcionarios/<int:person_id>/datos/', views.datos_funcionario, name='datos_funcionario'),
]
