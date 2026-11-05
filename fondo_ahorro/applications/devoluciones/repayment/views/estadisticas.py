from collections import defaultdict
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from ..models import DevoConsejo, DevoSolicitud
from .calculos import resumen_importe


ZONA_CHILE = ZoneInfo('America/Santiago')
ESTADO_ANULADO_ID = 3          # DEJA SIN EFECTO
ESTADO_ESPERA_CONSEJO_ID = 4  # EN ESPERA DEL CONSEJO
ESTADO_PAGADO_ID = 5          # PAGADO
ESTADO_ESPERA_PAGO_ID = 9     # EN ESPERA DE PAGO
CERO = Decimal('0')


def nombre_persona(persona):
    if not persona:
        return '—'
    nombre = ' '.join(str(valor).strip() for valor in (
        getattr(persona, 'first_name', ''),
        getattr(persona, 'second_name', ''),
        getattr(persona, 'last_name_1', ''),
        getattr(persona, 'last_name_2', ''),
    ) if valor)
    return nombre or '—'


def pesos(valor):
    return '${:,.0f}'.format(valor or CERO).replace(',', '.')


@login_required
@require_GET
def estadisticas_consejos(request):
    consejos = list(
        DevoConsejo.objects.filter(is_active=True)
        .select_related('estado')
        .order_by('-fecha_consejo', '-pk')
    )
    elegido = request.GET.get('consejo', '').strip()
    consejo = None

    if elegido:
        if elegido.isdigit():
            consejo = next((c for c in consejos if c.pk == int(elegido)), None)
    elif consejos:
        consejo = consejos[0]

    resumen = {
        'cantidad': 0,
        'vigentes': 0,
        'anuladas': 0,
        'en_consejo': 0,
        'en_pago': 0,
        'pagadas': 0,
        'total_estimado': CERO,
        'total_fijo': CERO,
        'total_variable': CERO,
        'cantidad_fijas': 0,
        'cantidad_porcentuales': 0,
    }
    por_tipo = defaultdict(lambda: {'cantidad': 0, 'total': CERO})
    por_estado = defaultdict(lambda: {'cantidad': 0, 'total': CERO})
    filas = []

    if consejo is not None:
        solicitudes = (
            DevoSolicitud.objects.filter(is_active=True, consejo_id=consejo.pk)
            .select_related('tipo', 'motivo', 'estado', 'solicitud')
            .prefetch_related('detalles__persona', 'aportes__aporte_tipo')
            .order_by('-created_at', '-pk')
        )
        for solicitud in solicitudes:
            detalle = next((d for d in solicitud.detalles.all() if d.is_active), None)
            persona = detalle.persona if detalle else None
            nombre = nombre_persona(persona)
            rut = f'{persona.rut}-{persona.dv}' if persona else '—'
            importe_info = resumen_importe(solicitud)
            importe = importe_info['importe']
            aporte_items = importe_info['aportes']
            variable = any(a['modalidad'] == 'PORCENTAJE' for a in aporte_items)
            importe_variable = sum(
                (a['importe'] for a in aporte_items if a['modalidad'] == 'PORCENTAJE'), CERO
            )
            importe_fijo = importe - importe_variable
            modalidad = ('Aporte porcentual' if variable else
                         'Aporte fijo' if aporte_items else 'Monto general')
            anulada = solicitud.estado_id == ESTADO_ANULADO_ID
            tipo = solicitud.tipo.nombre if solicitud.tipo else 'Sin tipo'
            estado = solicitud.estado.nombre if solicitud.estado else 'Sin estado'

            resumen['cantidad'] += 1
            if anulada:
                resumen['anuladas'] += 1
            else:
                resumen['vigentes'] += 1
                resumen['total_estimado'] += importe
                resumen['total_fijo'] += importe_fijo
                resumen['total_variable'] += importe_variable
                if variable:
                    resumen['cantidad_porcentuales'] += 1
                if importe_fijo > 0:
                    resumen['cantidad_fijas'] += 1
            if solicitud.estado_id == ESTADO_ESPERA_CONSEJO_ID:
                resumen['en_consejo'] += 1
            elif solicitud.estado_id == ESTADO_ESPERA_PAGO_ID:
                resumen['en_pago'] += 1
            elif solicitud.estado_id == ESTADO_PAGADO_ID:
                resumen['pagadas'] += 1

            por_tipo[tipo]['cantidad'] += 1
            por_estado[estado]['cantidad'] += 1
            if not anulada:
                por_tipo[tipo]['total'] += importe
                por_estado[estado]['total'] += importe

            fecha_ingreso = (
                solicitud.created_at.astimezone(ZONA_CHILE).strftime('%d/%m/%Y')
                if solicitud.created_at else '—'
            )
            filas.append({
                'id': solicitud.pk,
                'funcionario': nombre,
                'rut': rut,
                'tipo': tipo,
                'motivo': solicitud.motivo.descripcion if solicitud.motivo else '—',
                'estado': estado,
                'modalidad': modalidad,
                'importe': pesos(importe),
                'anulada': anulada,
                'variable': variable,
                'fecha_ingreso': fecha_ingreso,
                'fecha_pago': solicitud.fecha_pago.strftime('%d/%m/%Y') if solicitud.fecha_pago else '—',
                'detalle_aportes': ', '.join(
                    f"{a['tipo']} ({a['porcentaje']} %)" if a['modalidad'] == 'PORCENTAJE'
                    else f"{a['tipo']} (fijo)" for a in aporte_items
                ) if aporte_items else 'No aplica',
            })

    mayor_tipo = max((datos['total'] for datos in por_tipo.values()), default=CERO)
    tipos = [
        {
            'nombre': nombre,
            'cantidad': datos['cantidad'],
            'total': pesos(datos['total']),
            'porcentaje_visual': round(float(datos['total'] / mayor_tipo) * 100) if mayor_tipo else 0,
        }
        for nombre, datos in sorted(por_tipo.items(), key=lambda item: item[1]['total'], reverse=True)
    ]
    estados = [
        {'nombre': nombre, 'cantidad': datos['cantidad'], 'total': pesos(datos['total'])}
        for nombre, datos in sorted(por_estado.items(), key=lambda item: item[1]['cantidad'], reverse=True)
    ]

    return render(request, 'devolucion/estadisticas/consejos.html', {
        'consejos': consejos,
        'consejo': consejo,
        'consejo_solicitado': elegido,
        'resumen': resumen,
        'total_estimado_clp': pesos(resumen['total_estimado']),
        'total_fijo_clp': pesos(resumen['total_fijo']),
        'total_variable_clp': pesos(resumen['total_variable']),
        'tipos': tipos,
        'estados': estados,
        'filas': filas,
    })
