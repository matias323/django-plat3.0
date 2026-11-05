from django.urls import path
from . import views
from .views.estadisticas import estadisticas_consejos
from .views.consejo import consejo_cerrar, consejo_anular_solicitud, consejo_actualizar_fecha_pago

app_name = 'devolucion'
urlpatterns = [
    path('', views.lista, name='lista'),

    # Estadísticas
    path('estadisticas/', estadisticas_consejos, name='estadisticas_consejos'),

    # Consejos
    path('consejos/', views.consejo_lista, name='consejo_lista'),
    path('consejos/datatable/', views.consejo_datatable, name='consejo_datatable'),
    path('consejos/crear/', views.consejo_crear, name='consejo_crear'),
    path('consejos/activos/', views.consejos_activos, name='consejos_activos'),
    path('consejos/<int:pk>/solicitudes/',views.consejo_solicitudes,name='consejo_solicitudes'),

    path('consejos/<int:pk>/cerrar/', consejo_cerrar, name='consejo_cerrar'),
    path('consejos/<int:pk>/solicitudes/<int:solicitud_id>/anular/', consejo_anular_solicitud, name='consejo_anular_solicitud'),
    path('consejos/<int:pk>/solicitudes/<int:solicitud_id>/fecha/', consejo_actualizar_fecha_pago, name='consejo_actualizar_fecha_pago'),

    # Devolucion
    path('crear/', views.crear_solicitud, name='crear_solicitud'),
    path('regiones/<int:region_id>/comunas/', views.comunas_region, name='comunas_region'),
    path('bancos/<int:banco_id>/cuentas/', views.cuentas_banco, name='cuentas_banco'),
    path('datatable/', views.datatable, name='datatable'),
    path('<int:pk>/detalle/', views.detalle_solicitud, name='detalle_solicitud'),
    path('<int:pk>/estado/', views.cambiar_estado_solicitud, name='cambiar_estado_solicitud'),
    path('<int:pk>/consejo/', views.vincular_consejo_solicitud, name='vincular_consejo_solicitud'),
    path('<int:pk>/documentos/', views.documentos_observaciones, name='documentos_observaciones'),
    path('<int:pk>/documentos/subir/', views.documento_subir, name='documento_subir'),
    path('<int:pk>/documentos/<int:documento_id>/estado/', views.documento_estado, name='documento_estado'),
    path('<int:pk>/documentos/<int:documento_id>/eliminar/', views.documento_eliminar, name='documento_eliminar'),
    path('<int:pk>/documentos/<int:documento_id>/ver/', views.documento_ver, name='documento_ver'),
    path('modal/crear/', views.modal_crear, name='modal_crear'),
    path('funcionarios/buscar/', views.buscar_funcionarios, name='buscar_funcionarios'),
    path('funcionarios/<int:person_id>/datos/', views.datos_funcionario, name='datos_funcionario'),
]
