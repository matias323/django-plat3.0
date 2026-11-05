from decimal import Decimal, InvalidOperation, ROUND_DOWN
from datetime import date
from calendar import monthrange
from django.utils import timezone
from .calculos import resumen_importe
import re
import unicodedata
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from core.models.employee import Employee
from core.models.location import Region, Commune
from core.models.bank import Banco, BancoCuentaTipo
from core.models.person import PersonaBanco
from core.models.request import Request, RequestType, RequestStatus
from core.models.partner import Partner, PartnerContribution, PartnerContributionType
from ..models import (
    DevoSolicitud,
    DevoSolicitudMotivo,
    DevoSolicitudTipo,
    DevoSolicitudEstado,
    DevoSolicitudConcepto,
    DevoTipoConcepto,
    DevoSolicitudTipoConcepto,
    DevoSolicitudAporte,
    DevoSolicitudDetalle,
    DevoMetodoPago,
    DevoConsejo,
    DevoConsejoEstado,
    DevoObservacion,
)



def _full_name(person):
    return ' '.join(str(x).strip() for x in (person.first_name, person.second_name, person.last_name_1, person.last_name_2) if x)


def _rut(person):
    return f'{person.rut}-{person.dv}'


def _clp(amount):
    return f'{int(amount or 0):,}'.replace(',', '.')



@login_required
@require_GET
def lista(request):
    context = {
        'tipos': DevoSolicitudTipo.objects.filter(is_active=True).order_by('nombre'),
        'motivos': DevoSolicitudMotivo.objects.filter(is_active=True).order_by('descripcion'),
        'regiones': Region.objects.filter(is_active=True).order_by('name'),
        'bancos': Banco.objects.filter(is_active=True).order_by('nombre'),
        'metodos': DevoMetodoPago.objects.filter(is_active=True).order_by('tipo'),
        'estados_devolucion': DevoSolicitudEstado.objects.filter(is_active=True).order_by('nombre'),
    }
    return render(request, 'devolucion/solicitud/lista.html', context)


@login_required
@require_GET
def datatable(request):
    try:
        draw = max(0, int(request.GET.get('draw', 0)))
        start = max(0, int(request.GET.get('start', 0)))
        length = min(100, max(1, int(request.GET.get('length', 10))))
        order_index = int(request.GET.get('order[0][column]', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros inválidos.'}, status=400)
    term = request.GET.get('search[value]', '').strip()
    qs = DevoSolicitud.objects.filter(is_active=True).select_related('motivo', 'estado', 'solicitud')
    total = qs.count()
    if term:
        terms = term.split()
        query = Q()
        for word in terms:
            query &= Q(motivo__descripcion__icontains=word) | Q(estado__nombre__icontains=word)
        if term.isdigit():
            query |= Q(pk=int(term)) | Q(solicitud_id=int(term))
        qs = qs.filter(query)
    filtered = qs.count()
    order_columns = {0: 'pk', 1: 'solicitud_id', 2: 'motivo__descripcion', 3: 'estado__nombre', 4: 'created_at'}
    field = order_columns.get(order_index, 'pk')
    if request.GET.get('order[0][dir]', 'desc') == 'desc':
        field = '-' + field
    rows = qs.order_by(field, '-pk')[start:start + length]
    return JsonResponse({'draw': draw, 'recordsTotal': total, 'recordsFiltered': filtered, 'data': [
        {'id': row.pk, 'solicitud': row.solicitud_id, 'motivo': row.motivo.descripcion if row.motivo else '—',
         'estado': row.estado.nombre if row.estado else '—',
         'fecha': row.created_at.strftime('%d/%m/%Y') if row.created_at else '—'} for row in rows
    ]})


@login_required
@require_GET
def modal_crear(request):
    tipos = DevoSolicitudTipo.objects.filter(is_active=True).order_by('nombre')
    motivos = DevoSolicitudMotivo.objects.filter(is_active=True).order_by('descripcion')
    return render(request, 'devolucion/solicitud/modal.html', {
        'tipos': tipos, 'motivos': motivos,
        'regiones': Region.objects.filter(is_active=True).order_by('name'),
        'bancos': Banco.objects.filter(is_active=True).order_by('nombre'),
        'metodos': DevoMetodoPago.objects.filter(is_active=True).order_by('tipo'),
    })


@login_required
@require_GET
def buscar_funcionarios(request):
    term = request.GET.get('q', '').strip()
    if len(term) < 2:
        return JsonResponse({'results': [], 'message': 'Ingrese al menos dos caracteres.'})
    qs = Employee.objects.filter(is_active=True, person__is_active=True).select_related('person', 'grade')
    names = Q()
    for word in term.split():
        names &= (Q(person__first_name__icontains=word) | Q(person__second_name__icontains=word)
                  | Q(person__last_name_1__icontains=word) | Q(person__last_name_2__icontains=word))
    query = Q(code__icontains=term) | names
    cleaned = term.replace('.', '').replace('-', '').replace(' ', '')
    if cleaned.isdigit():
        query |= Q(person__rut=int(cleaned))
    if '-' in term:
        number, dv = term.rsplit('-', 1)
        number = number.replace('.', '').strip()
        if number.isdigit() and dv.strip():
            query |= Q(person__rut=int(number), person__dv__iexact=dv.strip())
    matches = qs.filter(query).order_by('person__first_name', 'person__last_name_1', 'pk')[:30]
    return JsonResponse({'results': [
        {'id': employee.person_id, 'employee_id': employee.pk, 'nombre': _full_name(employee.person),
         'rut': _rut(employee.person), 'codigo': employee.code or '',
         'grado': str(employee.grade) if employee.grade else '—'} for employee in matches
    ]})


@login_required
@require_GET
def datos_funcionario(request, person_id):
    employee = Employee.objects.filter(person_id=person_id, is_active=True, person__is_active=True).select_related('person', 'grade').first()
    if not employee:
        return JsonResponse({'message': 'Funcionario no encontrado.'}, status=404)
    partner = Partner.objects.filter(person_id=person_id, is_active=True).first()
    balances = {'A1': Decimal('0'), 'A2': Decimal('0'), 'A3': Decimal('0')}
    if partner:
        contributions = PartnerContribution.objects.filter(partner=partner, is_active=True).select_related('contribution_type').order_by('pk')
        for contribution in contributions:
            key = str(contribution.contribution_type.description).strip().upper()
            if key in balances:
                balances[key] = Decimal(contribution.amount or 0)
    person = employee.person
    return JsonResponse({
        'id': person.pk, 'nombre': _full_name(person), 'rut': _rut(person), 'codigo': employee.code or '',
        'grado': str(employee.grade) if employee.grade else '—', 'socio': bool(partner),
        'ahorros': {key: {'valor': str(value), 'formato': _clp(value)} for key, value in balances.items()}
    })


# ============================================================
# CATÁLOGOS DEPENDIENTES
# ============================================================
@login_required
@require_GET
def comunas_region(request, region_id):
    if not Region.objects.filter(pk=region_id, is_active=True).exists():
        return JsonResponse({'status': 'error', 'message': 'Región inválida.'}, status=404)

    comunas = Commune.objects.filter(region_id=region_id, is_active=True).order_by('name')
    return JsonResponse({'status': 'ok', 'results': [
        {'id': c.pk, 'nombre': c.name} for c in comunas
    ]})


@login_required
@require_GET
def cuentas_banco(request, banco_id):
    if not Banco.objects.filter(pk=banco_id, is_active=True).exists():
        return JsonResponse({'status': 'error', 'message': 'Banco inválido.'}, status=404)

    qs = BancoCuentaTipo.objects.filter(
        banco_id=banco_id, is_active=True, banco_cuenta__is_active=True
    ).select_related('banco_cuenta').order_by('banco_cuenta__descripcion')

    return JsonResponse({'status': 'ok', 'results': [
        {'id': item.pk, 'nombre': item.banco_cuenta.descripcion} for item in qs
    ]})


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text or '').upper())
                   if not unicodedata.combining(c))


def _monto(raw):
    value = str(raw or '').strip().replace('.', '').replace(' ', '')
    if not re.fullmatch(r'\d+', value):
        raise ValueError('Los montos deben ser números enteros positivos.')
    return Decimal(value)


def _seis_meses(fecha):
    anio = fecha.year + (fecha.month - 1 + 6) // 12
    mes = (fecha.month - 1 + 6) % 12 + 1
    return date(anio, mes, min(fecha.day, monthrange(anio, mes)[1]))


def _estado_devolucion(nombre):
    return DevoSolicitudEstado.objects.filter(nombre__iexact=nombre, is_active=True).order_by('pk').first()


def _guardar(instance, user):
    instance.save(user=user)
    return instance


# ============================================================
# CREACIÓN DE SOLICITUD: NO MODIFICA SALDOS DEL SOCIO
# ============================================================
@login_required
@require_POST
@transaction.atomic
def crear_solicitud(request):
    post = request.POST

    try:
        persona_id = int(post.get('persona_id') or 0)
        tipo_id = int(post.get('tipo_devolucion') or 0)
        motivo_id = int(post.get('motivo') or 0)
        comuna_id = int(post.get('comuna') or 0)
        region_id = int(post.get('region') or 0)
        metodo_id = int(post.get('metodo_pago') or 0)
        banco_id = int(post.get('banco') or 0)
        cuenta_tipo_id = int(post.get('cuenta_tipo') or 0)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Hay campos con identificadores inválidos.'}, status=400)

    employee = Employee.objects.filter(person_id=persona_id, is_active=True, person__is_active=True).select_related('person', 'grade').first()
    tipo = DevoSolicitudTipo.objects.filter(pk=tipo_id, is_active=True).first()
    motivo = DevoSolicitudMotivo.objects.filter(pk=motivo_id, is_active=True).first()
    comuna = Commune.objects.filter(pk=comuna_id, region_id=region_id, region__is_active=True, is_active=True).first()
    metodo = DevoMetodoPago.objects.filter(pk=metodo_id, is_active=True).first()

    # ============================================================
    # OBTENER CONCEPTOS DEL TIPO DE DEVOLUCIÓN
    tipos_conceptos = list(
        DevoTipoConcepto.objects.filter(
            solicitud_tipo=tipo,
            is_active=True,
            solicitud_concepto__is_active=True,
        ).select_related(
            'solicitud_concepto'
        ).order_by('pk')
    )
    # ============================================================

    if not all((employee, tipo, motivo, comuna, metodo)):
        return JsonResponse({'status': 'error', 'message':
            'Seleccione un funcionario, tipo, motivo, región, comuna y método de pago válidos.'}, status=400)

    direccion = post.get('direccion', '').strip()
    telefono = post.get('telefono', '').strip()
    correo = post.get('correo', '').strip()
    if not direccion or len(direccion) > 255:
        return JsonResponse({'status': 'error', 'message': 'Ingrese una dirección válida.'}, status=400)

    if not re.fullmatch(r'[0-9]{9}', telefono):
        return JsonResponse({
            'status': 'error',
            'message': 'El teléfono debe contener exactamente 9 dígitos numéricos.'
        }, status=400)

    if not correo or len(correo) > 254:
        return JsonResponse({'status': 'error', 'message': 'Ingrese un correo electrónico válido.'}, status=400)

    try:
        validate_email(correo)
    except ValidationError:
        return JsonResponse({'status': 'error', 'message': 'El correo no es válido.'}, status=400)

    cuenta = None
    numero_cuenta = post.get('numero_cuenta', '').strip()

    
    # VALIDAR NÚMERO DE CUENTA BANCARIA
    if numero_cuenta and not re.fullmatch(r'[0-9]{1,50}', numero_cuenta):
        return JsonResponse({
            'status': 'error',
            'message': (
                'El número de cuenta debe contener únicamente'
            )
        }, status=400)


    if any((banco_id, cuenta_tipo_id, numero_cuenta)):
        relacion = BancoCuentaTipo.objects.filter(
            pk=cuenta_tipo_id, banco_id=banco_id, is_active=True,
            banco__is_active=True, banco_cuenta__is_active=True
        ).first()
        if not relacion or not numero_cuenta or len(numero_cuenta) > 50:
            return JsonResponse({'status': 'error', 'message': 'Datos bancarios incompletos o incompatibles.'}, status=400)

    # Validar aportes contra saldos reales desde servidor, nunca confiar en campos readonly.
    from core.models.partner import PartnerContribution
    saldos = {'A1': Decimal('0'), 'A2': Decimal('0'), 'A3': Decimal('0')}
    contribuciones = PartnerContribution.objects.filter(
        partner__person_id=persona_id, partner__is_active=True, is_active=True
    ).select_related('contribution_type')
    tipos_aporte = {}
    for item in contribuciones:
        key = str(item.contribution_type.description).strip().upper()
        if key in saldos:
            saldos[key] += item.amount or Decimal('0')
            tipos_aporte[key] = item.contribution_type

    disponibles = [key for key in saldos if re.search(r'\b' + key + r'\b', _norm(tipo.nombre))]
    importes = {}
    try:
        if disponibles:
            for key in disponibles:
                monto = _monto(post.get('monto_' + key.lower()))
                if monto <= 0 or monto > saldos[key] or key not in tipos_aporte:
                    raise ValueError(f'El monto {key} debe ser mayor a cero y no superar su saldo.')
                importes[key] = monto
            general = Decimal('0')
        else:
            general = _monto(post.get('monto_general'))
            if general <= 0:
                raise ValueError('El monto general debe ser mayor a cero.')
    except (ValueError, InvalidOperation) as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    # Solo se permite asignar porcentaje a un aporte cuando se marca expresamente.
    # Para monto FIJO, no se crea concepto y el importe no cambiará al pagar.
    modalidades = {}
    relaciones = {}
    for key, monto in importes.items():
        es_porcentaje = str(post.get('porcentaje_' + key.lower(), '')).strip()
        if not es_porcentaje:
            modalidades[key] = ('FIJO', None)
            continue
        try:
            pct = Decimal(es_porcentaje)
        except InvalidOperation:
            return JsonResponse({'status': 'error', 'message': f'Porcentaje inválido para {key}.'}, status=400)
        if pct not in (Decimal('25'), Decimal('50'), Decimal('100')):
            return JsonResponse({'status': 'error', 'message': f'Porcentaje no admitido para {key}.'}, status=400)
        esperado = (saldos[key] * pct / Decimal(100)).quantize(Decimal('1'), rounding=ROUND_DOWN)
        if monto != esperado:
            return JsonResponse({'status': 'error', 'message': f'El importe porcentual de {key} no corresponde al saldo actual.'}, status=400)
        # Resolver la relación del catálogo por porcentaje; no suponer IDs globales.
        relacion = next((r for r in tipos_conceptos
                         if re.search(rf'(?<!\d){int(pct)}\s*%', r.solicitud_concepto.descripcion)), None)
        if not relacion:
            return JsonResponse({'status': 'error', 'message': f'No existe concepto {pct}% asociado al tipo seleccionado.'}, status=400)
        relaciones[key] = relacion
        modalidades[key] = ('PORCENTAJE', pct)

    if general and importes:
        return JsonResponse({'status': 'error', 'message': 'No se admite mezclar monto general con aportes.'}, status=400)

    tipo_request = RequestType.objects.filter(pk=2,is_active=True).first()
    estado_request = RequestStatus.objects.filter(pk=9,is_active=True).first()
    estado_devo = DevoSolicitudEstado.objects.filter(pk=4,is_active=True).first()
    if not tipo_request or not estado_request or not estado_devo:
        return JsonResponse({
            'status': 'error',
            'message': (
                'No se pudo crear la solicitud porque falta '
                'alguno de los registros de configuración.'
            )
        }, status=400)

    # La solicitud siempre se incorpora al consejo vigente al momento de su creación.
    # Bloqueamos la fila del catálogo Activado, igual que al crear un consejo.
    estado_consejo_activo = (DevoConsejoEstado.objects.select_for_update()
                             .filter(nombre__iexact='Activado', is_active=True).first())
    if not estado_consejo_activo:
        return JsonResponse({
            'status': 'error', 'message': 'No está configurado el estado Activado de consejos.'
        }, status=400)

    consejos_vigentes = list(DevoConsejo.objects.filter(
        estado=estado_consejo_activo, cerrado=False, is_active=True).order_by('-pk')[:2])
    if len(consejos_vigentes) != 1:
        return JsonResponse({
            'status': 'error',
            'message': ('No hay un consejo activo.' if not consejos_vigentes else
                        'Existen varios consejos activos. Debe regularizar sus estados.'),
        }, status=409)
    consejo_actual = consejos_vigentes[0]

    if banco_id:
        cuenta = PersonaBanco.objects.filter(
            persona_id=persona_id, banco_id=banco_id, cuenta_tipo_id=cuenta_tipo_id,
            n_cuenta=numero_cuenta, is_active=True
        ).first()
        if cuenta is None:
            cuenta = _guardar(PersonaBanco(
                persona_id=persona_id, banco_id=banco_id,
                cuenta_tipo_id=cuenta_tipo_id, n_cuenta=numero_cuenta
            ), request.user)

    solicitud_general = _guardar(Request(request_type=tipo_request, status=estado_request), request.user)
    devolucion = _guardar(DevoSolicitud(
        solicitud=solicitud_general, estado=estado_devo, tipo=tipo,
        motivo=motivo, grado=employee.grade, consejo=consejo_actual, monto_general=general,
        fecha_pago=_seis_meses(timezone.localdate()),
        direccion=direccion, comuna=comuna, telefono=telefono, correo=correo,
    ), request.user)

    # Los conceptos son opcionales: únicamente se asocian a aportes porcentuales.
    for key, relacion in relaciones.items():
        _guardar(DevoSolicitudTipoConcepto(
            solicitud_devolucion=devolucion, tipo_concepto=relacion
        ), request.user)

    for key, monto in importes.items():
        modalidad, porcentaje = modalidades[key]
        _guardar(DevoSolicitudAporte(
            solicitud_devolucion=devolucion, aporte_tipo=tipos_aporte[key],
            monto=monto, modalidad=modalidad, porcentaje=porcentaje,
        ), request.user)

    _guardar(DevoSolicitudDetalle(
        solicitud_devolucion=devolucion, metodo_pago=metodo,
        persona=employee.person, persona_banco=cuenta,
    ), request.user)

    DevoObservacion(
        solicitud=devolucion, accion=DevoObservacion.Accion.SOLICITUD_CREADA,
        descripcion=(f'Se creó la solicitud de devolución #{devolucion.pk} con estado ' f'{estado_devo.nombre}, asignada automáticamente al consejo #{consejo_actual.pk}.'),
    ).save(user=request.user)

    return JsonResponse({
        'status': 'ok', 'message': 'Solicitud de devolución creada correctamente.',
        'id': devolucion.pk, 'solicitud_id': solicitud_general.pk,
    })


# ============================================================
# DETALLE DE SOLICITUD / CAMBIO DE ESTADO
# ============================================================
@login_required
@require_GET
def detalle_solicitud(request, pk):
    devolucion = get_object_or_404(
        DevoSolicitud.objects.select_related(
            'tipo', 'motivo', 'estado', 'solicitud', 'solicitud__status',
            'grado', 'comuna', 'comuna__region', 'consejo'
        ).prefetch_related('aportes__aporte_tipo', 'detalles__persona',
                           'detalles__metodo_pago', 'detalles__persona_banco'),
        pk=pk, is_active=True
    )

    detalle = next((d for d in devolucion.detalles.all() if d.is_active), None)
    persona = detalle.persona if detalle else None
    cuenta = detalle.persona_banco if detalle else None
    empleado = Employee.objects.filter(person_id=persona.pk, is_active=True).first() if persona else None

    resumen = resumen_importe(devolucion)
    aportes = [
        {
            'tipo': item['tipo'], 'monto': _clp(item['importe']),
            'modalidad': item['modalidad'], 'porcentaje': item['porcentaje'],
            'saldo_actual': _clp(item['saldo_actual']),
            'saldo_insuficiente': item['saldo_insuficiente'],
        }
        for item in resumen['aportes']
    ]

    return JsonResponse({
        'status': 'ok',
        'solicitud': {
            'id': devolucion.pk,
            'general_id': devolucion.solicitud_id,
            'tipo': devolucion.tipo.nombre if devolucion.tipo else '—',
            'motivo': devolucion.motivo.descripcion if devolucion.motivo else '—',
            'estado_id': devolucion.estado_id,
            'consejo_id': devolucion.consejo_id,
            'consejo_nombre': str(devolucion.consejo) if devolucion.consejo else None,
            'estado': devolucion.estado.nombre,
            'estado_general': devolucion.solicitud.status.status_type,
            'fecha': devolucion.created_at.strftime('%d/%m/%Y %H:%M'),
            'fecha_aprobacion': devolucion.fecha_aprobacion.strftime('%d/%m/%Y') if devolucion.fecha_aprobacion else '—',
            'fecha_pago': devolucion.fecha_pago.strftime('%d/%m/%Y') if devolucion.fecha_pago else '—',
            'monto_general': _clp(devolucion.monto_general),
            'importe_estimado': _clp(resumen['importe']),
            'modalidad': resumen['modalidad'],
            'aportes': aportes,
            'nombre': _full_name(persona) if persona else '—',
            'rut': _rut(persona) if persona else '—',
            'codigo': empleado.code if empleado else '—',
            'grado': str(devolucion.grado) if devolucion.grado else '—',
            'direccion': devolucion.direccion or '—',
            'region': devolucion.comuna.region.name if devolucion.comuna else '—',
            'comuna': devolucion.comuna.name if devolucion.comuna else '—',
            'telefono': devolucion.telefono or '—',
            'correo': devolucion.correo or '—',
            'metodo': detalle.metodo_pago.tipo if detalle else '—',
            'banco': cuenta.banco.nombre if cuenta and cuenta.banco else '—',
            'tipo_cuenta': cuenta.cuenta_tipo.banco_cuenta.descripcion if cuenta and cuenta.cuenta_tipo else '—',
            'numero_cuenta': cuenta.n_cuenta if cuenta and cuenta.n_cuenta else '—',
        }
    })


@login_required
@require_POST
@transaction.atomic
def cambiar_estado_solicitud(request, pk):
    devolucion = get_object_or_404(
        DevoSolicitud.objects.select_for_update().select_related('solicitud'),
        pk=pk, is_active=True
    )

    try:
        estado_id = int(request.POST.get('estado_id') or 0)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'ID de estado inválido.'}, status=400)

    estado = DevoSolicitudEstado.objects.filter(pk=estado_id, is_active=True).first()
    if not estado:
        return JsonResponse({'status': 'error', 'message': 'Estado inexistente o inactivo.'}, status=400)

    protegidos = {'EN ESPERA DE CONSEJO', 'EN ESPERA DE PAGO', 'ANULADO', 'ANULADA', 'PAGADO', 'PAGADA'}
    if _norm(estado.nombre).strip() in protegidos or _norm(devolucion.estado.nombre).strip() in protegidos:
        return JsonResponse({
            'status': 'error',
            'message': 'El cambio de estado de consejo, anulación y pago se realiza mediante su flujo correspondiente.'
        }, status=403)

    # El pago real se debe registrar mediante un flujo financiero aparte.
    if _norm(estado.nombre).strip() in ('PAGADO', 'PAGADA'):
        return JsonResponse({
            'status': 'error',
            'message': 'El estado Pagado requiere registrar el pago. No puede asignarse desde este formulario.'
        }, status=400)

    if devolucion.estado_id == estado.pk:
        return JsonResponse({'status': 'ok', 'message': 'La solicitud ya tenía ese estado.',
                             'estado': estado.nombre, 'estado_id': estado.pk})

    nombre_anterior = devolucion.estado.nombre if devolucion.estado else 'Sin estado'
    devolucion.estado = estado
    devolucion.save(user=request.user)
    DevoObservacion(
        solicitud=devolucion, accion=DevoObservacion.Accion.ESTADO_SOLICITUD,
        descripcion=f'Estado de la solicitud cambiado de {nombre_anterior} a {estado.nombre}.',
    ).save(user=request.user)

    # Sincronizar core.Request solo cuando exista un estado general equivalente.
    estado_general = RequestStatus.objects.filter(
        is_active=True, status_type__iexact=estado.nombre
    ).order_by('pk').first()
    sincronizado = bool(estado_general)
    if estado_general:
        solicitud_general = devolucion.solicitud
        solicitud_general.status = estado_general
        solicitud_general.save(user=request.user)

    return JsonResponse({
        'status': 'ok',
        'message': 'Estado actualizado correctamente.' +
                   ('' if sincronizado else ' No existe un estado equivalente en core.RequestStatus; su estado general se conservó.'),
        'estado': estado.nombre,
        'estado_id': estado.pk,
        'estado_general_actualizado': sincronizado,
    })




@login_required
@require_POST
def vincular_consejo_solicitud(request, pk):
    """Ruta antigua: se bloquea la asignación manual desde cualquier cliente."""
    return JsonResponse({
        'status': 'error',
        'message': 'La asignación de consejos es automática al crear la devolución.'
    }, status=403)
