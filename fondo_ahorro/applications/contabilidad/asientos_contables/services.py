from django.db import transaction
from django.db.models import Q
from .models.asientos_contables import (
    AsientoContableCorrelativo, 
    AsientoContable, 
    AsientoContableTipo, 
    AsientoContableEstado, 
    AsientoMovimiento, 
    AsientoMovimientoAux,
    AsientoContableAprobacion)

from core.models.person import Person
from applications.contabilidad.plan_cuentas.models import Cuentas
from applications.contabilidad.periodo_contable.services import PeriodoContableServices
from django.contrib.contenttypes.models import ContentType
from datetime import date

class AsientoContableServices:
    
    #obtener el ultimo numeor de asiento ingresado
    @staticmethod
    def get_numero_asiento(year):
        correlativo, creado = (AsientoContableCorrelativo.objects.select_for_update().get_or_create(year=year, defaults={"last_number": 0}))
        correlativo.last_number += 1
        
        correlativo.save(update_fields=["last_number", "updated_at"])
        
        return correlativo.last_number
    
    #buscar persona tiempo real
    @staticmethod
    def search_persons(search):
        search = search.strip()
        
        if len(search) < 2:
            return []
        
        personas = Person.objects.filter(is_active = True).filter(
            Q(first_name__icontains=search) 
            | Q(last_name_1__icontains=search)
            | Q(last_name_2__icontains=search)
            | Q(rut__icontains=search)
        ).select_related("person_type").order_by("first_name", "last_name_1")[:10]
        
        return [
            {
                "id": p.id,
                "rut": p.get_rut(),
                "nombre": p.get_full_name(),
                "person_type":p.person_type.description
            }
            for p in personas
        ]
            
    
    #crear encabezado asiento
    @staticmethod
    @transaction.atomic
    def crear_encabezado_asiento(user, entry_date, description, entry_type, origen=None):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar fecha de asiento
        if not entry_date:
            raise ValueError("La fecha del asiento es requerida")
        
        # convertir fecha recibida desde HTTP
        if isinstance(entry_date, str):
            try:
                entry_date = date.fromisoformat(entry_date)
            except ValueError:
                raise ValueError("La fecha del asiento no tiene un formato válido")
        
        #periodo
        periodo = PeriodoContableServices.get_periodo_contable_by_year_and_month(entry_date.year, entry_date.month)
        if not periodo or periodo.is_active == False:
            raise ValueError("El periodo contable no esta activo")
        
        #validar tipo asiento
        entry_type = AsientoContableTipo.objects.filter(pk=entry_type).first()
        if not entry_type or entry_type.is_active == False:
            raise ValueError("El tipo de asiento no esta activo")
        
        #numero de asiento
        entry_number = AsientoContableServices.get_numero_asiento(entry_date.year)
        
        #numero de documento
        voucher_number = f"A{periodo.year}{entry_number}"
        
        #estado BORRADOR
        status = AsientoContableEstado.objects.get(pk=1)
        
        #crear asiento
        asiento = AsientoContable.objects.create(
            entry_year = periodo.year,
            entry_number = entry_number,
            entry_date = entry_date,
            description = description.upper().strip() if description else None,
            voucher_number = voucher_number,
            status = status,
            entry_type = entry_type,
            period = periodo,
            user_create = user
        )
        
        #registrar origen
        if origen is not None:
            asiento.origin_content_type = ContentType.objects.get_for_model(origen)
            asiento.origin_object_id = origen.pk
            asiento.save(update_fields=[
                "origin_content_type",
                "origin_object_id",
                "updated_at"
            ])
            
        return asiento
        
    #crear movimiento
    @staticmethod
    @transaction.atomic
    def crear_movimiento(user, asiento, account, debit, credit, description=None, auxiliares=None):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar asiento
        asiento = AsientoContable.objects.get(pk=asiento)
        if not asiento or asiento.status != 1: #1 = BORRADOR
            raise ValueError("El asiento no esta activo")
        
        #periodo
        if not asiento.period.is_active:
            raise ValueError("El periodo contable no esta activo")
        
        #validar cuenta
        account = Cuentas.objects.filter(pk=account).first()
        if not account or account.is_active == False:
            raise ValueError("La cuenta no esta activa")
        
        is_auxiliar = account.is_auxiliar
                
        #validar debe y haber
        if debit < 0 or credit < 0:
            raise ValueError("El monto debe ser mayor a 0")
        
        if debit > 0 and credit > 0:
            raise ValueError("El movimiento solo permite valor en debe o haber")
        
        if debit == 0 and credit == 0:
            raise ValueError("El movimiento debe tener al menos debe o haber")
        
        #crear movimiento
        movimiento = AsientoMovimiento.objects.create(
            entry = asiento,
            account = account,
            description = description.upper().strip() if description else None,
            debit = debit,
            credit = credit,
            user_create = user
        )
        
        #auxiliares
        if is_auxiliar:
            #validar que vengan auxiliares
            if len(auxiliares) == 0:
                raise ValueError("El movimiento debe tener al menos un auxiliar")
            
            #validar que los montos coincidan
            monto_total = sum(auxiliar.get("amount", 0) for auxiliar in auxiliares)
            
            if (debit + credit) != monto_total:
                raise ValueError("El monto total de los auxiliares debe ser igual al monto del movimiento")

            for auxiliar_data in auxiliares:
                person = auxiliar_data.get("person", None)
                amount = auxiliar_data.get("amount", 0)
                
                #validar persona
                person = Person.objects.filter(pk=person).first()
                if not person or person.is_active == False:
                    raise ValueError(f"La persona no identificada")
                
                #validar monto
                if amount <=0:
                    raise ValueError("El monto debe ser mayor a 0")
                
                #crear auxiliar
                auxiliar = AsientoMovimientoAux.objects.create(
                    movement = movimiento,
                    person = person,
                    amount = amount,
                    user_create = user
                )
                
        return movimiento
    
    #desactivar movimiento
    @staticmethod
    @transaction.atomic
    def desactivar_movimiento(user, movimiento, asiento):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #buscar asiento
        asiento = AsientoContable.objects.filter(pk=asiento).first()
        
        if not asiento:
            raise ValueError("El asiento no existe")
        
        if asiento.status in [3, 4]:
            raise ValueError("El no es posible desactivar el movimiento")
        
        #buscar movimiento
        movimiento = AsientoMovimiento.objects.select_for_update().filter(pk=movimiento, entry=asiento).first()
        
        if not movimiento:
            raise ValueError("El movimiento no existe")
        
        movimiento.is_active = False
        movimiento.user_update = user
        movimiento.save(update_fields=[
            "is_active",
            "user_update",
            "updated_at"
        ])
        
        #auxiliares
        AsientoMovimientoAux.objects.filter(movement=movimiento, is_active=True).update(is_active=False, user_update=user)
        
        return True
    
    #contabilizar asiento
    @staticmethod
    @transaction.atomic
    def contabilizar_asiento(user, asiento):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #buscar asiento
        asiento = AsientoContable.objects.select_for_update().filter(pk=asiento).first()
        
        if not asiento:
            raise ValueError("El asiento no existe")
        
        #validar asiento
        AsientoContableServices.validar_asiento(asiento)
        
        #contabilizar
        asiento.status = AsientoContableEstado.objects.get(pk=2)
        asiento.user_update = user
        asiento.save(update_fields=[
            "status",
            "user_update",
            "updated_at"
        ])
        
        #guardar registro de aprobacion
        AsientoContableAprobacion.objects.create(
            entry = asiento,
            user_create = user
        )
        
        return True
        
            
    #validar asiento
    @staticmethod
    def validar_asiento(asiento):
        #validar asiento
        asiento = AsientoContable.objects.filter(pk=asiento).first()
        if not asiento:
            raise ValueError("El asiento no existe")
        
        asiento_estado = asiento.status
        
        #movimeinto
        movimientos = AsientoMovimiento.objects.filter(entry=asiento, is_active=True).select_related("account")
        if len(movimientos) < 2 and asiento_estado!=3 or not movimientos.exist():#nulo
            raise ValueError("El asiento debe tener al menos 2 movimientos")
        
        total_debe = 0
        total_haber = 0
        for movimiento_data in movimientos:
            debit = movimiento_data.debit or 0
            credit = movimiento_data.credit or 0
            
            total_debe += debit
            total_haber += credit
            
            #validar debe y haber
            if debit == 0 and credit == 0:
                raise ValueError("El movimiento debe tener al menos debe o haber")
            
            if debit > 0 and credit > 0:
                raise ValueError("El movimiento solo permite valor en debe o haber")
            
            #validar cuenta
            if movimiento_data.account.is_active == False:
                raise ValueError("La cuenta no esta activa")
            
            #validar auxiliares
            if movimiento_data.account.is_auxiliar:
                auxiliares = AsientoMovimientoAux.objects.filter(movement=movimiento_data, is_active=True).select_related("person")
                if not auxiliares.exists():
                    raise ValueError("No existen auxiliares para el movimiento")
                
                total_auxiliares = sum(auxiliar.amount for auxiliar in auxiliares)
                
                if sum(debit, credit) != total_auxiliares:
                    raise ValueError("El monto total de los auxiliares debe ser igual al monto del movimiento")
        
        #validar debe y haber
        if total_debe != total_haber:
            raise ValueError("El asiento debe tener el mismo monto de debe y haber")
        
        return True
    
    #anular asiento
    @staticmethod
    @transaction.atomic
    def anular_asiento(user, asiento):
         #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar asiento
        asiento = AsientoContable.objects.filter(pk=asiento).first()
        if not asiento:
            raise ValueError("El asiento no existe")
        
        if asiento.status in [3, 4]:
            raise ValueError("No es posible anular el asiento")
        
        if asiento.period.is_active == False:
            raise ValueError("El periodo contable no esta activo")
        
        asiento.status = AsientoContableEstado.objects.get(pk=4)
        asiento.user_update = user
        asiento.save(update_fields=[
            "status",
            "user_update",
            "updated_at"
        ])
        
        #auxiliares
        AsientoMovimientoAux.objects.filter(movement__entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        #movimeinto
        AsientoMovimiento.objects.filter(entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        return True
        
    
    #crear asiento contable
    @staticmethod
    @transaction.atomic
    def crear_asiento_completo(user, entry_date, description, entry_type, movimientos, origen=None):
         #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar fecha de asiento
        if not entry_date:
            raise ValueError("La fecha del asiento es requerida")
        
        # convertir fecha recibida desde HTTP
        if isinstance(entry_date, str):
            try:
                entry_date = date.fromisoformat(entry_date)
            except ValueError:
                raise ValueError("La fecha del asiento no tiene un formato válido")
        
        #periodo
        periodo = PeriodoContableServices.get_periodo_contable_by_year_and_month(entry_date.year, entry_date.month)
        if not periodo or periodo.is_active == False:
            raise ValueError("El periodo contable no esta activo")
        
        #movimientos
        if movimientos is None or len(movimientos) == 0:
            raise ValueError("El asiento debe tener al menos 2 movimientos")
        
        #validar debe y haber
        debit_total = sum(movimiento.get("debit", 0) for movimiento in movimientos)
        credit_total = sum(movimiento.get("credit", 0) for movimiento in movimientos)
        
        if debit_total != credit_total:
            raise ValueError("El asiento debe tener el mismo monto de debe y haber")
        
        #validar tipo asiento
        entry_type = AsientoContableTipo.objects.filter(pk=entry_type).first()
        if not entry_type or entry_type.is_active == False:
            raise ValueError("El tipo de asiento no esta activo")
        
        #numero de asiento
        entry_number = AsientoContableServices.get_numero_asiento(entry_date.year)
        
        #numero de documento
        voucher_number = f"A{periodo.year}{entry_number}"
        
        #estado BORRADOR
        status = AsientoContableEstado.objects.get(pk=1)
        
        #crear asiento
        asiento = AsientoContable.objects.create(
            entry_year = periodo.year,
            entry_number = entry_number,
            entry_date = entry_date,
            description = description if description else None,
            voucher_number = voucher_number,
            status = status,
            entry_type = entry_type,
            period = periodo,
            user_create = user
        )
        
        #registrar origen
        if origen is not None:
            asiento.origin_content_type = ContentType.objects.get_for_model(origen)
            asiento.origin_object_id = origen.pk
            asiento.save(update_fields=[
                "origin_content_type",
                "origin_object_id",
                "updated_at"
            ])
        
        #movimientos
        for movimiento_data in movimientos:
            account = movimiento_data.get("account")
            debit = movimiento_data.get("debit", 0)
            credit = movimiento_data.get("credit", 0)
            account = movimiento_data.get("account", None)
            description_movimiento = movimiento_data.get("description", None)
            
            #validar cuenta
            account = Cuentas.objects.filter(pk=account).first()
            if not account or account.is_active == False:
                raise ValueError(f"La cuenta {account} no esta activa")
            
            is_auxiliar = account.is_auxiliar
            auxiliares = movimiento_data.get("auxiliares", [])
            
            #validar debito y credito
            if debit <0 or credit <0:
                raise ValueError("El monto debe ser mayor a 0")
            
            if debit==0 and credit==0:
                raise ValueError("Se debe incluir un monto mayor a 0 en debe o haber")
            
            #crear movimiento
            movimiento = AsientoMovimiento.objects.create(
                entry = asiento,
                account = account,
                description = description_movimiento.upper().strip() if description_movimiento else None,
                debit = debit,
                credit = credit,
                user_create = user
            )
            
            #auxiliares
            if is_auxiliar:
                #validar que vengan auxiliares
                if len(auxiliares) == 0:
                    raise ValueError("El movimiento debe tener al menos un auxiliar")
                
                #validar que los montos coincidan
                monto_total = sum(auxiliar.get("amount", 0) for auxiliar in auxiliares)
                
                if sum(debit, credit) != monto_total:
                    raise ValueError("El monto total de los auxiliares debe ser igual al monto del movimiento")
                
                for auxiliar_data in auxiliares:
                    person = auxiliar_data.get("person", None)
                    amount = auxiliar_data.get("amount", 0)
                    
                    #validar persona
                    person = Person.objects.filter(pk=person).first()
                    if not person or person.is_active == False:
                        raise ValueError(f"La persona no identificada")
                    
                    #validar monto
                    if amount <=0:
                        raise ValueError("El monto debe ser mayor a 0")
                    
                    #crear auxiliar
                    auxiliar = AsientoMovimientoAux.objects.create(
                        movement = movimiento,
                        person = person,
                        amount = amount,
                        user_create = user
                    )
              
        return asiento       
                
            
            
        
        
        
        
        
        
   

        
        