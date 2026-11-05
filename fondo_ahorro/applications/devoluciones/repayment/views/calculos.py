"""Cálculo uniforme para consejo."""
from decimal import Decimal, ROUND_DOWN
import re
from core.models.partner import PartnerContribution



def porcentaje_descripcion(texto):
    match = re.search(r'(100|50|25)\s*%', str(texto or ''))
    return Decimal(match.group(1)) if match else None



def saldo_aporte(persona_id, aporte_tipo_id):
    qs = PartnerContribution.objects.filter(
        partner__person_id=persona_id, partner__is_active=True,
        contribution_type_id=aporte_tipo_id, is_active=True,
    )
    return sum((Decimal(i.amount or 0) for i in qs), Decimal('0'))



def resumen_importe(devolucion):
    """Saldo actual para previsualización; recalcular de nuevo en la fecha real de pago."""
    aporte_items = list(devolucion.aportes.filter(is_active=True).select_related('aporte_tipo'))
    if not aporte_items:
        monto = Decimal(devolucion.monto_general or 0)
        return {'modalidad': 'GENERAL', 'importe': monto, 'aportes': []}
    detalle = devolucion.detalles.filter(is_active=True).first()
    persona_id = detalle.persona_id if detalle else None
    total = Decimal('0')
    filas = []
    for a in aporte_items:
        saldo = saldo_aporte(persona_id, a.aporte_tipo_id) if persona_id else Decimal('0')
        if a.modalidad == 'PORCENTAJE' and a.porcentaje is not None:
            importe = (saldo * Decimal(a.porcentaje) / Decimal(100)).quantize(Decimal('1'), rounding=ROUND_DOWN)
        else:
            importe = Decimal(a.monto or 0)
        total += importe
        filas.append({
            'tipo': a.aporte_tipo.description, 'modalidad': a.modalidad,
            'porcentaje': str(a.porcentaje) if a.porcentaje is not None else None,
            'importe': importe, 'saldo_actual': saldo,
            'monto_fijo': Decimal(a.monto or 0) if a.modalidad == 'FIJO' else None,
            'saldo_insuficiente': importe > saldo,
        })
    return {'modalidad': 'APORTES', 'importe': total, 'aportes': filas}
