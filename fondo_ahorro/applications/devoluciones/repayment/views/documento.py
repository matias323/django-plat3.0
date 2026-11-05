import logging
import uuid
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models.document import Document, DocumentType
from ..models import DevoDocumento, DevoDocumentoTipo, DevoObservacion, DevoSolicitud

logger = logging.getLogger(__name__)
MAX_FILE_SIZE = 10 * 1024 * 1024
FIRMAS = {
    '.pdf': b'%PDF-', '.png': b'\x89PNG\r\n\x1a\n',
    '.jpg': b'\xff\xd8\xff', '.jpeg': b'\xff\xd8\xff',
}


def _evento(solicitud, accion, descripcion, usuario, documento=None):
    observacion = DevoObservacion(
        solicitud=solicitud, documento=documento, accion=accion, descripcion=descripcion,
    )
    observacion.save(user=usuario)
    return observacion


def _validar_archivo(archivo):
    if not archivo:
        raise ValueError('Seleccione un archivo.')
    if archivo.size <= 0 or archivo.size > MAX_FILE_SIZE:
        raise ValueError('El archivo debe tener un tamaño máximo de 10 MB.')
    extension = Path(archivo.name).suffix.lower()
    if extension not in FIRMAS:
        raise ValueError('Solo se permiten archivos PDF, JPG y PNG.')
    if len(Path(archivo.name).name) > 255:
        raise ValueError('El nombre del archivo es demasiado largo.')
    firma = archivo.read(8)
    archivo.seek(0)
    if not firma.startswith(FIRMAS[extension]):
        raise ValueError('El contenido del archivo no coincide con su extensión.')


def _documentos_tipo(solicitud, tipo):
    return DevoDocumento.objects.filter(
        solicitud=solicitud, tipo=tipo, is_active=True,
    ).select_related('document', 'validated_by').order_by('-pk')


def _ultimo(solicitud, tipo):
    return _documentos_tipo(solicitud, tipo).first()


def _puede_subir(ultimo):
    # Sin archivo: se permite adjuntar el primero.
    # Rechazado: se permite una nueva versión.
    # Pendiente: debe revisarse antes de volver a adjuntar.
    # Aprobado: queda bloqueado.
    return ultimo is None or ultimo.estado == DevoDocumento.Estado.RECHAZADO


def _archivo_core(request, solicitud, tipo, archivo):
    tipo_core = DocumentType.objects.filter(name__iexact=tipo.nombre, is_active=True).first()
    if tipo_core is None:
        tipo_core = DocumentType(name=tipo.nombre)
        tipo_core.save(user=request.user)

    nombre = Path(archivo.name).name
    interno = uuid.uuid4().hex
    ruta = default_storage.save(
        f'devoluciones/{solicitud.pk}/{interno}{Path(nombre).suffix.lower()}', archivo,
    )
    try:
        core_documento = Document(
            type_document=tipo_core,
            document_name=nombre,
            internal_name=interno,
            file_type=archivo.content_type or 'application/octet-stream',
            size=archivo.size,
            route=ruta,
            user=request.user,
            ip=request.META.get('REMOTE_ADDR'),
        )
        core_documento.save(user=request.user)
        return core_documento, ruta
    except Exception:
        default_storage.delete(ruta)
        raise


@login_required
@require_GET
def documentos_observaciones(request, pk):
    solicitud = get_object_or_404(DevoSolicitud, pk=pk, is_active=True)
    tipos = DevoDocumentoTipo.objects.filter(is_active=True).order_by('orden', 'pk')
    documentos = []
    for tipo in tipos:
        registros = list(_documentos_tipo(solicitud, tipo))
        ultimo = registros[0] if registros else None
        historial = []
        for item in registros:
            historial.append({
                'id': item.pk,
                'nombre': item.document.document_name,
                'estado': item.estado,
                'rejection_comment': item.rejection_comment or '',
                'validated_by': str(item.validated_by) if item.validated_by_id else '—',
                'validated_at': timezone.localtime(item.validated_at).strftime('%d/%m/%Y %H:%M') if item.validated_at else '—',
                'vigente': item.pk == ultimo.pk,
            })
        documentos.append({
            'tipo_id': tipo.pk,
            'tipo': tipo.nombre,
            'estado': ultimo.estado if ultimo else 'sin_documento',
            'cantidad': len(registros),
            'historial': historial,
            'puede_adjuntar': _puede_subir(ultimo),
        })

    observaciones = []
    for o in DevoObservacion.objects.filter(
        solicitud=solicitud, is_active=True,
    ).select_related('user_create').order_by('-created_at', '-pk')[:200]:
        observaciones.append({
            'id': o.pk, 'accion': o.accion, 'descripcion': o.descripcion,
            'fecha': timezone.localtime(o.created_at).strftime('%d/%m/%Y %H:%M'),
            'usuario': str(o.user_create) if o.user_create_id else 'Sistema',
        })
    return JsonResponse({'status': 'ok', 'documentos': documentos, 'observaciones': observaciones})


@login_required
@require_POST
def documento_subir(request, pk):
    ruta_guardada = None
    try:
        archivo = request.FILES.get('archivo')
        _validar_archivo(archivo)
        try:
            tipo_id = int(request.POST.get('tipo_id', ''))
        except (TypeError, ValueError):
            raise ValueError('Tipo de documento inválido.')

        with transaction.atomic():
            solicitud = get_object_or_404(
                DevoSolicitud.objects.select_for_update(), pk=pk, is_active=True,
            )
            tipo = get_object_or_404(DevoDocumentoTipo, pk=tipo_id, is_active=True)
            anterior = _ultimo(solicitud, tipo)
            if not _puede_subir(anterior):
                return JsonResponse({
                    'status': 'error',
                    'message': ('Ya hay un documento pendiente de revisión.'
                                if anterior.estado == DevoDocumento.Estado.PENDIENTE
                                else 'El documento está aprobado y no puede reemplazarse.'),
                }, status=409)

            core_documento, ruta_guardada = _archivo_core(request, solicitud, tipo, archivo)
            nuevo = DevoDocumento(
                solicitud=solicitud, tipo=tipo, document=core_documento,
            )
            nuevo.save(user=request.user)
            accion = (DevoObservacion.Accion.DOCUMENTO_REEMPLAZADO if anterior
                      else DevoObservacion.Accion.DOCUMENTO_ADJUNTADO)
            verbo = 'adjuntó una nueva versión de' if anterior else 'adjuntó'
            _evento(solicitud, accion, f'Se {verbo} {tipo.nombre}: {archivo.name}. Estado Pendiente.', request.user, nuevo)

        return JsonResponse({'status': 'ok', 'message': 'Documento adjuntado en estado Pendiente.'})
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    except Exception:
        # El archivo físico no participa de la transacción de PostgreSQL.
        if ruta_guardada and default_storage.exists(ruta_guardada):
            default_storage.delete(ruta_guardada)
        logger.exception('Error al adjuntar documento a devolución %s', pk)
        return JsonResponse({'status': 'error', 'message': 'Error al guardar documento. Revise la terminal Django.'}, status=500)


@login_required
@require_POST
@transaction.atomic
def documento_estado(request, pk, documento_id):
    solicitud = get_object_or_404(DevoSolicitud.objects.select_for_update(), pk=pk, is_active=True)
    item = get_object_or_404(
        DevoDocumento.objects.select_for_update().select_related('tipo', 'document'),
        pk=documento_id, solicitud=solicitud, is_active=True,
    )
    actual = _ultimo(solicitud, item.tipo)
    if not actual or actual.pk != item.pk:
        return JsonResponse({'status': 'error', 'message': 'Solo se puede validar el último documento de cada categoría.'}, status=409)
    if item.estado != DevoDocumento.Estado.PENDIENTE:
        return JsonResponse({'status': 'error', 'message': 'Solo se pueden validar documentos pendientes.'}, status=409)

    nuevo = (request.POST.get('estado') or '').strip().lower()
    if nuevo not in (DevoDocumento.Estado.APROBADO, DevoDocumento.Estado.RECHAZADO):
        return JsonResponse({'status': 'error', 'message': 'Estado inválido.'}, status=400)
    motivo = (request.POST.get('observacion') or '').strip()
    if nuevo == DevoDocumento.Estado.RECHAZADO and len(motivo) < 5:
        return JsonResponse({'status': 'error', 'message': 'Debe indicar el motivo del rechazo (mínimo 5 caracteres).'}, status=400)

    item.estado = nuevo
    item.rejection_comment = motivo if nuevo == DevoDocumento.Estado.RECHAZADO else None
    item.validated_by = request.user
    item.validated_at = timezone.now()
    item.save(user=request.user)
    descripcion = f'Documento {item.tipo.nombre}: Pendiente → {item.get_estado_display()}.'
    if motivo:
        descripcion += f' Motivo del rechazo: {motivo}'
    _evento(solicitud, DevoObservacion.Accion.ESTADO_DOCUMENTO, descripcion, request.user, item)
    return JsonResponse({'status': 'ok', 'message': 'Documento actualizado correctamente.'})


@login_required
@require_POST
@transaction.atomic
def documento_eliminar(request, pk, documento_id):
    solicitud = get_object_or_404(DevoSolicitud.objects.select_for_update(), pk=pk, is_active=True)
    item = get_object_or_404(
        DevoDocumento.objects.select_for_update().select_related('tipo', 'document'),
        pk=documento_id, solicitud=solicitud, is_active=True,
    )
    ultimo = _ultimo(solicitud, item.tipo)
    if not ultimo or ultimo.pk != item.pk:
        return JsonResponse({'status': 'error', 'message': 'Solo puede retirarse el último documento.'}, status=409)
    if item.estado == DevoDocumento.Estado.APROBADO:
        return JsonResponse({'status': 'error', 'message': 'No se puede eliminar un documento aprobado.'}, status=409)
    item.is_active = False
    item.save(user=request.user)
    _evento(solicitud, DevoObservacion.Accion.DOCUMENTO_ELIMINADO,
            f'Se retiró {item.tipo.nombre}: {item.document.document_name}.', request.user, item)
    return JsonResponse({'status': 'ok', 'message': 'Documento retirado; se conserva en la auditoría.'})


@login_required
@require_GET
def documento_ver(request, pk, documento_id):
    solicitud = get_object_or_404(DevoSolicitud, pk=pk, is_active=True)
    item = get_object_or_404(
        DevoDocumento.objects.select_related('document'),
        pk=documento_id, solicitud=solicitud,
    )
    try:
        archivo = default_storage.open(item.document.route, 'rb')
    except (FileNotFoundError, OSError):
        raise Http404('Archivo no encontrado.')
    extension = Path(item.document.document_name).suffix.lower()
    tipo = {'.pdf': 'application/pdf', '.png': 'image/png',
            '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg'}.get(extension, 'application/octet-stream')
    respuesta = FileResponse(archivo, content_type=tipo, as_attachment=False,
                              filename=item.document.document_name)
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta
