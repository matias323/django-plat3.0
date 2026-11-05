# Exportación para mantener views.nombre_vista en urls.py.
from .solicitud import (
    lista, datatable, modal_crear, buscar_funcionarios, datos_funcionario,
    comunas_region, cuentas_banco, crear_solicitud, detalle_solicitud,
    cambiar_estado_solicitud, vincular_consejo_solicitud,
)
from .consejo import consejo_lista, consejo_datatable, consejo_crear, consejos_activos, consejo_solicitudes

from .documento import (documentos_observaciones, documento_subir, documento_estado,
    documento_eliminar, documento_ver)
