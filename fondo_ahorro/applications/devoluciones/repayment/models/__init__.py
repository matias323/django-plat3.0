# Si tu models/__init__.py actual exporta otros modelos, CONSÉRVALOS también.
from .consejo import DevoConsejo, DevoConsejoEstado
from .solicitud import (
    DevoSolicitudMotivo, DevoSolicitudConcepto, DevoSolicitudTipo,
    DevoSolicitudEstado, DevoSolicitud, DevoSolicitudAporte,
    DevoSolicitudDetalle, DevoTipoConcepto, DevoSolicitudTipoConcepto,
    DevoMetodoPago,
)

from .documento import DevoDocumentoTipo, DevoDocumento, DevoObservacion
