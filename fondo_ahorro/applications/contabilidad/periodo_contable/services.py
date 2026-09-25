from .models import PeriodoContable
from .utils import get_month_name
from django.db import transaction
from datetime import date
import calendar


class PeriodoContableServices: 
    
    # obtener el periodo contable actual
    @staticmethod
    def get_periodo_contable_actual():
        periodo = PeriodoContable.objects.filter(is_active=True).first()
        return periodo
    
    # obtener el periodo contable por año y mes
    @staticmethod
    def get_periodo_contable_by_year_and_month(year, month):
        periodo = PeriodoContable.objects.filter(year=year, month=month).first()
        return periodo

    # obtener todos los periodos contables (datatable)
    @staticmethod
    def get_periodos_contables():
        periodos = PeriodoContable.objects.select_related('user_create', 'user_create__person').order_by('-pk')
        data = []
        for orden, row in enumerate(periodos, start=1):
            data.append({
                "id": row.id,
                "order": orden,
                "period_date": f"{get_month_name(row.month)}-{row.year}",
                "year": row.year,
                "month": get_month_name(row.month),
                "start_date": row.start_date.strftime("%d-%m-%Y"),
                "end_date": (
                    row.end_date.strftime("%d-%m-%Y")
                    if row.end_date is not None
                    else ""
                    ),
                "opening_date": row.opening_date.strftime("%d-%m-%Y"),
                "closing_date": (
                    row.closing_date.strftime("%d-%m-%Y")
                    if row.closing_date is not None
                    else "HABILITADO"
                ),
                "is_active": row.is_active,
                "user": row.user_create.person.get_name(),
            })
        
        return data
    
    #crear nuevo periodo
    @staticmethod
    @transaction.atomic
    def crear_nuevo_periodo(user):
        periodo_actual = PeriodoContable.objects.select_for_update().filter(is_active=True).first()
        fecha_actual = date.today()
        if not periodo_actual:
            nuevo_anio = fecha_actual.year
            nuevo_mes = fecha_actual.month
            periodo_inicio = date(nuevo_anio, nuevo_mes, 1)
            periodo_fin = date(nuevo_anio, nuevo_mes, calendar.monthrange(nuevo_anio, nuevo_mes)[1])
            nuevo_periodo =PeriodoContable.objects.create(
                year = nuevo_anio,
                month = nuevo_mes,
                start_date = periodo_inicio,
                end_date = periodo_fin,
                opening_date = fecha_actual,
                is_active = True,
                user_create = user
            )
            
            return nuevo_periodo
        
        #existe periodo anteior
        if periodo_actual.month == 12:
            nuevo_anio = periodo_actual.year + 1
            nuevo_mes = 1
        else:
            nuevo_anio = periodo_actual.year
            nuevo_mes = periodo_actual.month + 1
            
        #verificar que no exista nuevo periodo
        periodo_existente = PeriodoContable.objects.filter(year=nuevo_anio, month=nuevo_mes).first()
        if periodo_existente:
            raise ValueError(f"El periodo {get_month_name(nuevo_mes)}-{nuevo_anio} ya existe")
        
        #fechas de inicio y fin nuevo periodo
        periodo_inicio = date(nuevo_anio, nuevo_mes, 1)
        periodo_fin = date(nuevo_anio, nuevo_mes, calendar.monthrange(nuevo_anio, nuevo_mes)[1])
        
        #desactivar periodo actual
        periodo_actual.is_active = False
        periodo_actual.closing_date = fecha_actual
        periodo_actual.save(user = user,
            update_fields=["is_active", "closing_date", "updated_at"]
        )
        
        #crear nuevo periodo
        nuevo_periodo = PeriodoContable.objects.create(
            year = nuevo_anio,
            month = nuevo_mes,
            start_date = periodo_inicio,
            end_date = periodo_fin,
            opening_date = fecha_actual,
            is_active = True,
            user_create = user
        )
        
        return nuevo_periodo
        
        
        
        
    
