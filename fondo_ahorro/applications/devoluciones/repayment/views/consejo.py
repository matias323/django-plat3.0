from datetime import date
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.db.models import Sum
from core.models.request import RequestStatus
from ..models import DevoObservacion, DevoSolicitudEstado
from .calculos import resumen_importe
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from ..models import DevoConsejo, DevoConsejoEstado, DevoSolicitud
from zoneinfo import ZoneInfo



@login_required
@require_GET
def consejo_lista(request):
    hoy = timezone.localdate()

    context = {
        'anios': range(hoy.year, hoy.year + 8),
        'anio_actual': hoy.year,
        'mes_actual': hoy.month,

        # Estados necesarios para el modal de detalle de solicitudes.
        'estados_devolucion': DevoSolicitudEstado.objects.filter(
            is_active=True
        ).order_by('nombre'),
    }

    return render(request, 'devolucion/consejo/consejo_lista.html', context)



@login_required
@require_GET
def consejo_datatable(request):
    try:
        draw = max(0, int(request.GET.get('draw', 0)))
        start = max(0, int(request.GET.get('start', 0)))
        length = min(100, max(1, int(request.GET.get('length', 10))))
        order_index = int(request.GET.get('order[0][column]', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros inválidos.'}, status=400)

    qs = DevoConsejo.objects.filter(is_active=True).select_related('user_create', 'estado')
    total = qs.count()
    busqueda = request.GET.get('search[value]', '').strip()
    if busqueda:
        filtros = Q(user_create__username__icontains=busqueda)
        if busqueda.isdigit():
            filtros |= Q(pk=int(busqueda)) | Q(fecha_consejo__year=int(busqueda))
        # Permite buscar fechas en formato YYYY-MM-DD.
        try:
            fecha = date.fromisoformat(busqueda)
            filtros |= Q(fecha_consejo=fecha)
        except ValueError:
            pass
        filtros |= Q(estado__nombre__icontains=busqueda)
        qs = qs.filter(filtros)

    filtrados = qs.count()
    columnas = {0: 'pk', 1: 'fecha_consejo', 2: 'user_create_id',
                3: 'fecha_creacion', 4: 'estado__nombre'}
    campo = columnas.get(order_index, 'fecha_consejo')
    if request.GET.get('order[0][dir]', 'desc') == 'desc':
        campo = '-' + campo

    filas = qs.order_by(campo, '-pk')[start:start + length]
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total,
        'recordsFiltered': filtrados,
        'data': [
            {
                'id': c.pk,
                'fecha_consejo': c.fecha_consejo.strftime('%d/%m/%Y'),
                'usuario': str(c.user_create) if c.user_create else '—',
                'fecha_creacion': (
                    c.fecha_creacion.astimezone(
                        ZoneInfo('America/Santiago')
                    ).strftime('%d/%m/%Y %H:%M:%S')
                    if c.fecha_creacion else '—'
                ),
                'estado': c.estado.nombre if c.estado else '—',
                'cerrado': c.cerrado,
            }
            for c in filas
        ],
    })



@login_required
@require_POST
@transaction.atomic
def consejo_crear(request):
    try:
        anio = int(request.POST.get('anio', ''))
        mes = int(request.POST.get('mes', ''))
        fecha = date(anio, mes, 1)
    except (ValueError, TypeError):
        return JsonResponse({
            'status': 'error',
            'message': 'Seleccione un año y mes válidos.'
        }, status=400)

    if anio < 2000 or anio > 2100:
        return JsonResponse({
            'status': 'error',
            'message': 'El año debe estar entre 2000 y 2100.'
        }, status=400)

    # Bloqueamos el estado Activado para serializar
    # las creaciones simultáneas de consejos.
    estado_activo = DevoConsejoEstado.objects.select_for_update().filter(
        nombre__iexact='Activado',
        is_active=True
    ).first()

    estado_inactivo = DevoConsejoEstado.objects.filter(
        nombre__iexact='Desactivado',
        is_active=True
    ).first()

    if not estado_activo or not estado_inactivo:
        return JsonResponse({
            'status': 'error',
            'message': 'Debe configurar los estados Activado y Desactivado.'
        }, status=400)

    # Evitar duplicar un consejo del mismo período.
    if DevoConsejo.objects.filter(
        fecha_consejo=fecha,
        is_active=True
    ).exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Ya existe un consejo registrado para ese mes y año.'
        }, status=409)

    # Desactivar los consejos anteriormente activados.
    consejos_anteriores = DevoConsejo.objects.filter(
        estado=estado_activo,
        is_active=True
    ).select_for_update()

    cantidad_desactivados = 0

    for anterior in consejos_anteriores:
        anterior.estado = estado_inactivo
        anterior.save(user=request.user)
        cantidad_desactivados += 1

    # Crear el nuevo consejo activado.
    consejo = DevoConsejo(
        fecha_consejo=fecha,
        estado=estado_activo
    )
    consejo.save(user=request.user)

    return JsonResponse({
        'status': 'ok',
        'message': (
            f'Consejo #{consejo.pk} creado correctamente. '
            f'Se desactivaron {cantidad_desactivados} consejos anteriores.'
        ),
        'id': consejo.pk,
        'consejos_desactivados': cantidad_desactivados
    }, status=201)



@login_required
@require_GET
def consejos_activos(request):
    consejos = DevoConsejo.objects.filter(
        is_active=True, estado__nombre__iexact='Activado', estado__is_active=True
    ).order_by('-fecha_consejo', '-pk')
    return JsonResponse({'status': 'ok', 'results': [
        {'id': c.pk, 'nombre': f'Consejo #{c.pk} - {c.fecha_consejo:%m/%Y}'}
        for c in consejos
    ]})



@login_required
@require_GET
def consejo_solicitudes(request, pk):
    """Retorna las devoluciones actualmente vinculadas al consejo indicado."""
    consejo = get_object_or_404(DevoConsejo, pk=pk, is_active=True)
    solicitudes = (DevoSolicitud.objects
        .filter(consejo_id=pk, is_active=True)
        .select_related('tipo', 'motivo', 'estado', 'solicitud')
        .prefetch_related('detalles__persona')
        .order_by('-created_at', '-pk'))

    filas = []
    total = 0
    total_importe = Decimal('0')
    for solicitud in solicitudes:
        detalle = next((d for d in solicitud.detalles.all() if d.is_active), None)
        persona = detalle.persona if detalle else None
        nombre = ' '.join(str(v).strip() for v in (
            getattr(persona, 'first_name', None), getattr(persona, 'second_name', None),
            getattr(persona, 'last_name_1', None), getattr(persona, 'last_name_2', None)
        ) if v) or '—'
        rut = f'{persona.rut}-{persona.dv}' if persona else '—'
        resumen = resumen_importe(solicitud)
        monto = int(resumen['importe'])
        if solicitud.estado and solicitud.estado.nombre.strip().lower() not in ('anulado', 'anulada'):
            total_importe += resumen['importe']
        # Los aportes específicos se guardan en otra tabla; el total se calcula
        # aparte únicamente si el monto general no está definido.
        filas.append({
            'id': solicitud.pk,
            'solicitud_general': solicitud.solicitud_id,
            'funcionario': nombre, 'rut': rut,
            'tipo': solicitud.tipo.nombre if solicitud.tipo else '—',
            'motivo': solicitud.motivo.descripcion if solicitud.motivo else '—',
            'estado': solicitud.estado.nombre if solicitud.estado else 'Sin estado',
            'monto_general': int(solicitud.monto_general or 0),
            'importe_estimado': monto,
            'modalidad': resumen['modalidad'],
            'aportes': [{'tipo': a['tipo'], 'modalidad': a['modalidad'], 'porcentaje': a['porcentaje']} for a in resumen['aportes']],
            'fecha_pago': solicitud.fecha_pago.isoformat() if solicitud.fecha_pago else '',
            'fecha': timezone.localtime(solicitud.created_at).strftime('%d/%m/%Y'),
        })
        total += 1
    return JsonResponse({
        'status': 'ok',
        'consejo': {'id': consejo.pk, 'fecha': consejo.fecha_consejo.strftime('%m/%Y'),
                    'estado': consejo.estado.nombre if consejo.estado else '—',
                    'cerrado': consejo.cerrado},
        'cantidad': total, 'solicitudes': filas, 'total_estimado': int(total_importe),
    })



@login_required
@require_POST
@transaction.atomic
def consejo_actualizar_fecha_pago(request, pk, solicitud_id):
    consejo = get_object_or_404(DevoConsejo.objects.select_for_update(), pk=pk, is_active=True)
    if consejo.cerrado:
        return JsonResponse({'status': 'error', 'message': 'El consejo ya está cerrado.'}, status=409)
    solicitud = get_object_or_404(DevoSolicitud.objects.select_for_update(),
                                  pk=solicitud_id, consejo=consejo, is_active=True)
    if solicitud.estado.nombre.strip().lower() in ('anulado', 'anulada'):
        return JsonResponse({'status': 'error', 'message': 'No puede editar una solicitud anulada.'}, status=409)
    fecha = parse_date(request.POST.get('fecha_pago', ''))
    if not fecha:
        return JsonResponse({'status': 'error', 'message': 'Fecha de pago inválida (AAAA-MM-DD).'}, status=400)
    if fecha < timezone.localdate():
        return JsonResponse({'status': 'error', 'message': 'La fecha de pago no puede ser anterior a hoy.'}, status=400)
    anterior = solicitud.fecha_pago
    solicitud.fecha_pago = fecha
    solicitud.save(user=request.user)
    DevoObservacion(solicitud=solicitud, accion=DevoObservacion.Accion.ESTADO_SOLICITUD,
                    descripcion=f'Consejo #{pk}: fecha de pago modificada de {anterior} a {fecha}.').save(user=request.user)
    return JsonResponse({'status': 'ok', 'message': 'Fecha de pago actualizada.', 'fecha_pago': fecha.isoformat()})



@login_required
@require_POST
@transaction.atomic
def consejo_anular_solicitud(request, pk, solicitud_id):
    consejo = get_object_or_404(DevoConsejo.objects.select_for_update(), pk=pk, is_active=True)
    if consejo.cerrado:
        return JsonResponse({'status': 'error', 'message': 'El consejo ya está cerrado.'}, status=409)
    solicitud = get_object_or_404(DevoSolicitud.objects.select_for_update(),
                                  pk=solicitud_id, consejo=consejo, is_active=True)
    estado = DevoSolicitudEstado.objects.filter(nombre__iexact='Anulado', is_active=True).first()
    if not estado:
        estado = DevoSolicitudEstado.objects.filter(nombre__iexact='Anulada', is_active=True).first()
    if not estado:
        return JsonResponse({'status': 'error', 'message': 'Debe registrar el estado Anulado en devo_solicitud_estado.'}, status=400)
    if solicitud.estado_id == estado.pk:
        return JsonResponse({'status': 'ok', 'message': 'La solicitud ya está anulada.'})
    if solicitud.estado.nombre.strip().lower() != 'en espera de consejo':
        return JsonResponse({'status': 'error', 'message': 'Solo se pueden anular solicitudes en espera de consejo.'}, status=409)
    motivo = (request.POST.get('motivo') or '').strip()
    if len(motivo) < 5:
        return JsonResponse({'status': 'error', 'message': 'Indique el motivo de anulación (mínimo 5 caracteres).'}, status=400)
    solicitud.estado = estado
    solicitud.save(user=request.user)
    estado_general = RequestStatus.objects.filter(status_type__iexact='Rechazado', is_active=True).first()
    if estado_general:
        solicitud.solicitud.status = estado_general
        solicitud.solicitud.save(user=request.user)
    DevoObservacion(solicitud=solicitud, accion=DevoObservacion.Accion.ESTADO_SOLICITUD,
                    descripcion=f'Anulada en consejo #{pk}. Motivo: {motivo}').save(user=request.user)
    return JsonResponse({'status': 'ok', 'message': 'Solicitud anulada correctamente.'})



@login_required
@require_POST
@transaction.atomic
def consejo_cerrar(request, pk):
    consejo = get_object_or_404(DevoConsejo.objects.select_for_update(), pk=pk, is_active=True)
    if consejo.cerrado:
        return JsonResponse({'status': 'ok', 'message': 'El consejo ya estaba cerrado.', 'cantidad': 0})
    espera = DevoSolicitudEstado.objects.filter(nombre__iexact='En espera de pago', is_active=True).first()
    if not espera:
        return JsonResponse({'status': 'error', 'message': 'Debe registrar En espera de pago en devo_solicitud_estado.'}, status=400)
    solicitudes = list(DevoSolicitud.objects.select_for_update().filter(
        consejo=consejo, is_active=True).select_related('estado', 'solicitud'))
    pendientes = [s for s in solicitudes if s.estado.nombre.strip().lower() == 'en espera de consejo']
    otros = [s for s in solicitudes if s.estado.nombre.strip().lower() not in
             ('en espera de consejo', 'anulado', 'anulada')]
    if otros:
        return JsonResponse({'status': 'error', 'message': 'El consejo contiene solicitudes en estados incompatibles.'}, status=409)
    for solicitud in pendientes:
        if not solicitud.fecha_pago:
            return JsonResponse({'status': 'error', 'message': f'La solicitud #{solicitud.pk} no tiene fecha de pago.'}, status=400)
        resumen = resumen_importe(solicitud)
        if resumen['importe'] <= 0:
            return JsonResponse({'status': 'error', 'message': f'La solicitud #{solicitud.pk} no tiene importe válido.'}, status=400)
    estado_general = RequestStatus.objects.filter(status_type__iexact='En espera de pago', is_active=True).first()
    for solicitud in pendientes:
        solicitud.estado = espera
        solicitud.fecha_aprobacion = timezone.localdate()
        solicitud.save(user=request.user)
        if estado_general:
            solicitud.solicitud.status = estado_general
            solicitud.solicitud.save(user=request.user)
        DevoObservacion(solicitud=solicitud, accion=DevoObservacion.Accion.ESTADO_SOLICITUD,
                        descripcion=f'Consejo #{pk} cerrado: solicitud enviada a En espera de pago.').save(user=request.user)
    consejo.cerrado = True
    consejo.fecha_cierre = timezone.now()
    consejo.save(user=request.user)
    return JsonResponse({'status': 'ok', 'message': f'Consejo cerrado; {len(pendientes)} solicitudes enviadas a espera de pago.',
                         'cantidad': len(pendientes)})
