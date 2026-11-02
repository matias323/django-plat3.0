from datetime import date
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from ..models import DevoConsejo, DevoConsejoEstado, DevoSolicitud





@login_required
@require_GET
def consejo_lista(request):
    hoy = timezone.localdate()
    return render(request, 'devolucion/consejo/consejo_lista.html', {
        'anios': range(hoy.year - 5, hoy.year + 6),
        'anio_actual': hoy.year,
        'mes_actual': hoy.month,
    })


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
                'fecha_creacion': c.fecha_creacion.strftime('%d/%m/%Y %H:%M') if c.fecha_creacion else '—',
                'estado': c.estado.nombre if c.estado else '—',
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
            'status': 'error', 'message': 'Seleccione un año y mes válidos.'
        }, status=400)

    if anio < 2000 or anio > 2100:
        return JsonResponse({
            'status': 'error', 'message': 'El año debe estar entre 2000 y 2100.'
        }, status=400)

    if DevoConsejo.objects.filter(fecha_consejo=fecha, is_active=True).exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Ya existe un consejo registrado para ese mes y año.'
        }, status=409)

    estado_activo = DevoConsejoEstado.objects.filter(nombre__iexact='Activado', is_active=True).first()
    if not estado_activo:
        return JsonResponse({'status': 'error', 'message': 'Falta configurar el estado Activado.'}, status=400)

    consejo = DevoConsejo(fecha_consejo=fecha, estado=estado_activo)
    consejo.save(user=request.user)
    return JsonResponse({
        'status': 'ok',
        'message': 'Consejo creado correctamente.',
        'id': consejo.pk,
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
    for solicitud in solicitudes:
        detalle = next((d for d in solicitud.detalles.all() if d.is_active), None)
        persona = detalle.persona if detalle else None
        nombre = ' '.join(str(v).strip() for v in (
            getattr(persona, 'first_name', None), getattr(persona, 'second_name', None),
            getattr(persona, 'last_name_1', None), getattr(persona, 'last_name_2', None)
        ) if v) or '—'
        rut = f'{persona.rut}-{persona.dv}' if persona else '—'
        monto = int(solicitud.monto_general or 0)
        # Los aportes específicos se guardan en otra tabla; el total se calcula
        # aparte únicamente si el monto general no está definido.
        filas.append({
            'id': solicitud.pk,
            'solicitud_general': solicitud.solicitud_id,
            'funcionario': nombre, 'rut': rut,
            'tipo': solicitud.tipo.nombre if solicitud.tipo else '—',
            'motivo': solicitud.motivo.descripcion if solicitud.motivo else '—',
            'estado': solicitud.estado.nombre if solicitud.estado else 'Sin estado',
            'monto_general': monto,
            'fecha': timezone.localtime(solicitud.created_at).strftime('%d/%m/%Y'),
        })
        total += 1
    return JsonResponse({
        'status': 'ok',
        'consejo': {'id': consejo.pk, 'fecha': consejo.fecha_consejo.strftime('%m/%Y'),
                    'estado': consejo.estado.nombre if consejo.estado else '—'},
        'cantidad': total, 'solicitudes': filas,
    })
