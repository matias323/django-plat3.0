from django.db import transaction
from collections import OrderedDict
from django.db.models import Q, Prefetch, Sum, Value
from django.db.models.functions import Coalesce
from .models.asientos_contables import (
    AsientoContableCorrelativo, 
    AsientoContable, 
    AsientoContableTipo, 
    AsientoContableEstado, 
    AsientoMovimiento, 
    AsientoMovimientoAux,
    AsientoContableAprobacion,
    AsientoContableBloqueo)
from applications.contabilidad.periodo_contable.models import PeriodoContable
from core.models.person import Person
from applications.contabilidad.plan_cuentas.models import Cuentas
from applications.contabilidad.periodo_contable.services import PeriodoContableServices
from django.contrib.contenttypes.models import ContentType
from datetime import date, timedelta
from django.utils import timezone
import time

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
    # @staticmethod
    # @transaction.atomic
    # def crear_encabezado_asiento(user, entry_date, description, entry_type, origen=None):
    #     #validar user
    #     if not user or not user.is_authenticated:
    #         raise ValueError("El usuario es requerido")
        
    #     #validar fecha de asiento
    #     if not entry_date:
    #         raise ValueError("La fecha del asiento es requerida")
        
    #     # convertir fecha recibida desde HTTP
    #     if isinstance(entry_date, str):
    #         try:
    #             entry_date = date.fromisoformat(entry_date)
    #         except ValueError:
    #             raise ValueError("La fecha del asiento no tiene un formato válido")
        
    #     #periodo
    #     periodo = PeriodoContableServices.get_periodo_contable_by_year_and_month(entry_date.year, entry_date.month)
    #     if not periodo or periodo.is_active == False:
    #         raise ValueError("El periodo contable no esta activo")
        
    #     #validar tipo asiento
    #     entry_type = AsientoContableTipo.objects.filter(pk=entry_type).first()
    #     if not entry_type or entry_type.is_active == False:
    #         raise ValueError("El tipo de asiento no esta activo")
        
    #     #numero de asiento
    #     entry_number = AsientoContableServices.get_numero_asiento(entry_date.year)
        
    #     #numero de documento
    #     voucher_number = f"A{periodo.year}{entry_number}"
        
    #     #estado BORRADOR
    #     status = AsientoContableEstado.objects.get(pk=1)
        
    #     #crear asiento
    #     asiento = AsientoContable.objects.create(
    #         entry_year = periodo.year,
    #         entry_number = entry_number,
    #         entry_date = entry_date,
    #         description = description.upper().strip() if description else None,
    #         voucher_number = voucher_number,
    #         status = status,
    #         entry_type = entry_type,
    #         period = periodo,
    #         user_create = user
    #     )
        
    #     #registrar origen
    #     if origen is not None:
    #         asiento.origin_content_type = ContentType.objects.get_for_model(origen)
    #         asiento.origin_object_id = origen.pk
    #         asiento.save(update_fields=[
    #             "origin_content_type",
    #             "origin_object_id",
    #             "updated_at"
    #         ])
            
    #     return asiento
        
    #crear movimiento
    # @staticmethod
    # @transaction.atomic
    # def crear_movimiento(user, asiento, account, debit, credit, description=None, auxiliares=None):
    #     #validar user
    #     if not user or not user.is_authenticated:
    #         raise ValueError("El usuario es requerido")
        
    #     #validar asiento
    #     asiento = AsientoContable.objects.get(pk=asiento)
    #     if not asiento or asiento.status != 1: #1 = BORRADOR
    #         raise ValueError("El asiento no esta activo")
        
    #     #periodo
    #     if not asiento.period.is_active:
    #         raise ValueError("El periodo contable no esta activo")
        
    #     #validar cuenta
    #     account = Cuentas.objects.filter(pk=account).first()
    #     if not account or account.is_active == False:
    #         raise ValueError("La cuenta no esta activa")
        
    #     is_auxiliar = account.is_auxiliar
                
    #     #validar debe y haber
    #     if debit < 0 or credit < 0:
    #         raise ValueError("El monto debe ser mayor a 0")
        
    #     if debit > 0 and credit > 0:
    #         raise ValueError("El movimiento solo permite valor en debe o haber")
        
    #     if debit == 0 and credit == 0:
    #         raise ValueError("El movimiento debe tener al menos debe o haber")
        
    #     #crear movimiento
    #     movimiento = AsientoMovimiento.objects.create(
    #         entry = asiento,
    #         account = account,
    #         description = description.upper().strip() if description else None,
    #         debit = debit,
    #         credit = credit,
    #         user_create = user
    #     )
        
    #     #auxiliares
    #     if is_auxiliar:
    #         #validar que vengan auxiliares
    #         if len(auxiliares) == 0:
    #             raise ValueError("El movimiento debe tener al menos un auxiliar")
            
    #         #validar que los montos coincidan
    #         monto_total = sum(auxiliar.get("amount", 0) for auxiliar in auxiliares)
            
    #         if (debit + credit) != monto_total:
    #             raise ValueError("El monto total de los auxiliares debe ser igual al monto del movimiento")

    #         for auxiliar_data in auxiliares:
    #             person = auxiliar_data.get("person", None)
    #             amount = auxiliar_data.get("amount", 0)
                
    #             #validar persona
    #             person = Person.objects.filter(pk=person).first()
    #             if not person or person.is_active == False:
    #                 raise ValueError(f"La persona no identificada")
                
    #             #validar monto
    #             if amount <=0:
    #                 raise ValueError("El monto debe ser mayor a 0")
                
    #             #crear auxiliar
    #             auxiliar = AsientoMovimientoAux.objects.create(
    #                 movement = movimiento,
    #                 person = person,
    #                 amount = amount,
    #                 user_create = user
    #             )
                
    #     return movimiento
    
    #desactivar movimiento
    # @staticmethod
    # @transaction.atomic
    # def desactivar_movimiento(user, movimiento, asiento):
    #     #validar user
    #     if not user or not user.is_authenticated:
    #         raise ValueError("El usuario es requerido")
        
    #     #buscar asiento
    #     asiento = AsientoContable.objects.filter(pk=asiento).first()
        
    #     if not asiento:
    #         raise ValueError("El asiento no existe")
        
    #     if asiento.status in [3, 4]:
    #         raise ValueError("El no es posible desactivar el movimiento")
        
    #     #buscar movimiento
    #     movimiento = AsientoMovimiento.objects.select_for_update().filter(pk=movimiento, entry=asiento).first()
        
    #     if not movimiento:
    #         raise ValueError("El movimiento no existe")
        
    #     movimiento.is_active = False
    #     movimiento.user_update = user
    #     movimiento.save(update_fields=[
    #         "is_active",
    #         "user_update",
    #         "updated_at"
    #     ])
        
    #     #auxiliares
    #     AsientoMovimientoAux.objects.filter(movement=movimiento, is_active=True).update(is_active=False, user_update=user)
        
    #     return True
    
    #contabilizar asiento
    @staticmethod
    @transaction.atomic
    def contabilizar_asiento(user, pk):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #buscar asiento
        asiento = AsientoContable.objects.select_for_update().filter(pk=pk).first()
        
        if not asiento:
            raise ValueError("El asiento no existe")
        
        #validar asiento
        AsientoContableServices.validar_asiento(pk)
        
        #contabilizar
        asiento.status = AsientoContableEstado.objects.get(pk=4) #4: contabilizado
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
    def validar_asiento(pk):
        #validar asiento
        asiento = AsientoContable.objects.filter(pk=pk).first()
        if not asiento:
            raise ValueError("El asiento no existe")
        
        #movimeinto
        movimientos = AsientoMovimiento.objects.filter(entry=asiento, is_active=True).select_related("account")
        if len(movimientos) < 2 or not movimientos.exists():#nulo
            raise ValueError("El asiento debe tener al menos 2 movimientos")
        
        #asiento nulo
        if asiento.is_null: 
            if len(movimientos) > 1:
                raise ValueError("El asiento nulo no debe tener movimientos activos")
        
        if asiento.status.id == 4:
            raise ValueError("El asiento ya ha sido contabilizado")
        
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
    def anular_asiento(user, asiento_id):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar asiento
        asiento = AsientoContable.objects.filter(pk=asiento_id).first()
        if not asiento:
            raise ValueError("El asiento no existe")
        
        if asiento.status.id == 4: #4: contabilizado
            raise ValueError("No es posible anular el asiento, ya ha sido contabilizado")
        
        if asiento.period.is_active == False:
            raise ValueError("El periodo contable no esta activo")
        
        
        asiento.is_null = True
        asiento.user_update = user
        asiento.save(update_fields=[
            "is_null",
            "user_update",
            "updated_at"
        ])
        
        #auxiliares
        AsientoMovimientoAux.objects.filter(movement__entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        #movimeinto
        AsientoMovimiento.objects.filter(entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        return True
    
    #quitar nulo asiento
    @staticmethod
    @transaction.atomic
    def quitar_nulo_asiento(user, asiento_id):
         #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar asiento
        asiento = AsientoContable.objects.filter(pk=asiento_id).first()
        if not asiento:
            raise ValueError("El asiento no existe")
        
        if asiento.status.id == 4: #4: contabilizado
            raise ValueError("No es posible activar el asiento, ya ha sido contabilizado")
        
        if asiento.period.is_active == False:
            raise ValueError("El periodo contable no esta activo")
        
        
        asiento.is_null = False
        asiento.user_update = user
        asiento.save(update_fields=[
            "is_null",
            "user_update",
            "updated_at"
        ])
        
        #auxiliares
        AsientoMovimientoAux.objects.filter(movement__entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        #movimeinto
        AsientoMovimiento.objects.filter(entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        return True
    
    #crear movimiento
    @staticmethod
    @transaction.atomic
    def crear_movimiento(user, asiento_id, data):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #validar asiento
        asiento = AsientoContable.objects.get(pk=asiento_id)
        if not asiento or asiento.status.id == 4: #4 = CONTABILIZADO
            raise ValueError("El asiento no esta activo")
        
        #validar que asiento no este nulo
        if asiento.is_null:
            raise ValueError("El asiento esta nulo")
        
        #periodo
        if not asiento.period.is_active:
            raise ValueError("El periodo contable no esta activo")
        

        account_id = data.get("account")
        description = data.get("description")
        debit = data.get("debit", 0)
        credit = data.get("credit", 0)
        auxiliares = data.get("auxiliares", [])
        
        
        #validar cuenta
        account = Cuentas.objects.filter(pk=account_id).first()
        if not account or account.is_active == False:
            raise ValueError("La cuenta no esta activa")
        
        #verificar si cuenta es imputable(utilizable para contabilizar)
        cuentas_catalogo = Cuentas.get_catalogo_cuentas()
        if not any(c["id"] == account_id for c in cuentas_catalogo):
            raise ValueError(f"La cuenta no es imputable(No se puede utilizar para contabilizar)")
        
        #validar debe y haber
        if debit == 0 and credit == 0:
            raise ValueError("El movimiento debe tener al menos debe o haber")
        
        if debit > 0 and credit > 0:
            raise ValueError("El movimiento solo permite valor en debe o haber")
        
    
        
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
        
        if account.is_auxiliar:
            #validar que vengan auxiliares
            if len(auxiliares) == 0:
                raise ValueError("El movimiento debe tener al menos un auxiliar")
            
            #validar que los montos coincidan
            monto_total = sum(auxiliar.get("amount", 0) for auxiliar in auxiliares)
            
            if (debit + credit) != monto_total:
                raise ValueError("El monto total de los auxiliares debe ser igual al monto del movimiento")
            
            # Set para registrar personas ya procesadas en este movimiento
            auxiliares_procesados = set()

            for auxiliar_data in auxiliares:
                person_id = auxiliar_data.get("person", None)
                amount = auxiliar_data.get("amount", 0)
                
                #validar persona
                person = Person.objects.filter(pk=person_id).first()
                if not person or person.is_active == False:
                    raise ValueError(f"La persona no identificada")
                
                #validar monto
                if amount <=0:
                    raise ValueError("El monto debe ser mayor a 0")
                
                if person_id in auxiliares_procesados:
                    raise ValueError(f"La persona {person.get_full_name()} se encuentra duplicada en el movimiento")
                
                auxiliares_procesados.add(person_id)
                
                #crear auxiliar
                AsientoMovimientoAux.objects.create(
                    movement = movimiento,
                    person = person,
                    amount = amount,
                    user_create = user
                )
                
        return movimiento
        
    
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
            raise ValueError("La fecha del asiento corresponde a un periodo inactivo")
        
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
        status = AsientoContableEstado.objects.get(pk=1) #1: borrador
        
        #crear asiento
        asiento = AsientoContable.objects.create(
            entry_year = periodo.year,
            entry_number = entry_number,
            entry_date = entry_date,
            description = description.upper().strip(),
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
                "updated_at",
                "user_update"
            ])
        
        #movimientos
        for movimiento_data in movimientos:
            AsientoContableServices.crear_movimiento(user, asiento.id, movimiento_data)
              
        return asiento
    
    #verificar si se puede editar el asiento
    @staticmethod
    @transaction.atomic
    def check_asiento_edit(pk, version, user):
        response = []
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        if not pk or pk <= 0:
            raise ValueError("El id del asiento es requerido")
        
        if not version or version <= 0:
            raise ValueError("La versión del asiento es requerida")
        
        #buscar asiento
        asiento = AsientoContable.objects.filter(pk=pk).first()
        
        if not asiento:
            raise ValueError("El asiento no existe")
        
        if asiento.status.id == 4: #4: contabilizado
            raise ValueError("No es posible editar el asiento")
        
        if asiento.is_null:
            raise ValueError("No es posible editar el asiento")
        
        if asiento.version != version:
            response = {
                "success": False,
                "message": "El asiento ha sido modificado por otro usuario",
                "refresh": True
            }
            return response
            
        
        #buscar si asiento esta siendo modificado por otro usuario
        bloqueo = AsientoContableBloqueo.objects.filter(entry=asiento, is_active=True).order_by("-locked_at").first()
        if bloqueo:
            
            #verificar si el bloqueo es del mismo usuario
            if bloqueo.user_create == user:
                #actualizar el locked_at
                bloqueo.locked_at = timezone.now()
                bloqueo.save(update_fields=[
                    "locked_at",
                    "updated_at",
                    "user_update"
                ])
                
                response = {
                    "success": True,
                    "message": "El asiento se puede editar",
                    "refresh": False
                }
                return response
                
                
            #tiempo de expiracion
            tiempo_expiracion = timezone.now() - timedelta(minutes=15)
            
            if bloqueo.locked_at < tiempo_expiracion:
                bloqueo.is_active = False
                bloqueo.save(update_fields=[
                    "is_active",
                    "updated_at",
                    "user_update"
                ])
                
                #crear nuevo bloqueo
                AsientoContableBloqueo.objects.create(
                    entry = asiento,
                    user_create = user,
                    is_active = True,
                    locked_at = timezone.now()
                    
                )
                
                response = {
                    "success": True,
                    "message": "El asiento se puede editar",
                    "refresh": False
                }
                return response
            else:
                response = {
                    "success": False,
                    "message": f"El asiento se encuentra siendo modificado por {bloqueo.get_user_bloqueo()}",
                    "refresh": False
                }
                return response
        
        #crear bloqueo
        AsientoContableBloqueo.objects.create(
            entry = asiento,
            user_create = user,
            is_active = True,
            locked_at = timezone.now()
        )
        
        response = {
            "success": True,
            "message": "El asiento se puede editar",
            "refresh": False
        }
        return response
    
    #quitar bloqueo asiento
    @staticmethod
    @transaction.atomic
    def uncheck_asiento(user, pk):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        if not pk:
            raise ValueError("El id del asiento es requerido")
        
        #buscar asiento
        asiento = AsientoContable.objects.filter(pk=pk).first()
        
        if not asiento:
            raise ValueError("El asiento no existe")
        
        #buscar bloqueo
        bloqueo = AsientoContableBloqueo.objects.filter(entry=asiento, is_active=True).order_by("-locked_at").first()
        if not bloqueo:
            raise ValueError("No existe un registro de bloqueo para el asiento")
        
        bloqueo.is_active = False
        bloqueo.save(update_fields=[
            "is_active",
            "updated_at",
            "user_update"
        ])
        
        return True
    
    #editar asiento
    @staticmethod
    @transaction.atomic
    def editar_asiento(user, asiento_id, glosa_asiento, movimientos):
         #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        if not asiento_id:
            raise ValueError("El id del asiento es requerido")
        
        if not glosa_asiento:
            raise ValueError("La glosa del asiento es requerida")
                     
        #movimientos
        if movimientos is None or len(movimientos) == 0:
            raise ValueError("El asiento debe tener al menos 2 movimientos")
                
        #validar debe y haber
        debit_total = sum(movimiento.get("debit", 0) for movimiento in movimientos)
        credit_total = sum(movimiento.get("credit", 0) for movimiento in movimientos)
                
        if debit_total != credit_total:
            raise ValueError("El asiento debe tener el mismo monto de debe y haber")
        
        #verificar que el asiento exista, periodo activo y no este contabilizado
        asiento = AsientoContable.objects.filter(pk=asiento_id).first()
        if not asiento:
            raise ValueError("El asiento no existe")
        
        if asiento.status.id == 4: #4: contabilizado
            raise ValueError("No es posible editar el asiento")
        
        if asiento.period.is_active == False:
            raise ValueError("El periodo contable no esta activo")
        
        #verificar si se puede editar
        response = AsientoContableServices.check_asiento_edit(asiento_id, asiento.version, user)
        if not response["success"]:
            raise ValueError(response["message"])
    
        
        #desactivar movimientos actuales
        AsientoMovimiento.objects.filter(entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        #desactivar auxiliares pertenecientes al movimiento
        AsientoMovimientoAux.objects.filter(movement__entry=asiento, is_active=True).update(is_active=False, user_update=user)
        
        #actualizar glosa
        asiento.description = glosa_asiento.upper().strip()
        asiento.user_update = user
        asiento.save(update_fields=[
            "description",
            "user_update",
            "updated_at"
        ])
        
        #crear movimientos
        for movimiento_data in movimientos:
            AsientoContableServices.crear_movimiento(user, asiento_id, movimiento_data)
            
        #quitar bloqueo
        AsientoContableServices.uncheck_asiento(user, asiento_id)
        
        #incrementar version
        asiento.version = asiento.version + 1
        asiento.user_update = user
        asiento.save(update_fields=[
            "version",
            "user_update",
            "updated_at"
        ])
        
        return asiento
    
    #generar pdf de asiento contable MEJORAR URGENTE
    # @staticmethod
    # def asiento_pdf(pk): 
        
    #     movimientos = (
    #         AsientoMovimiento.objects.filter(is_active=True)
    #         .select_related("account", "user_create", "user_create__person")
    #         .prefetch_related(Prefetch("auxiliares", queryset=AsientoMovimientoAux.objects.filter(is_active=True)
    #             .select_related("person", "user_create", "user_create__person")))
    #     )
        
    #     asiento = (AsientoContable.objects.select_related("status", "entry_type", "period", "user_create", "user_create__person")
    #         .prefetch_related(Prefetch("movimientos", queryset=movimientos))
    #         .filter(pk=pk, is_active=True, status=4)
    #         .first()
    #     )
        
    #     if not asiento:
    #         return None
        
    #     return asiento.asiento_to_dict()
    
    #buscar asientos
    @staticmethod
    def buscar_asientos(numero=None, periodo_id=None, tipo_id=None, estado_id=None, fecha_inicio=None, fecha_fin=None, cuenta=None, asiento_id=None):
        filters = Q(is_active=True)
        filters_movimientos = Q(is_active=True)
        
        if numero:
            filters &= Q(entry_number=numero)
            
        if periodo_id:
            filters &= Q(period=periodo_id)
            
        if tipo_id:
            filters &= Q(entry_type=tipo_id)
            
        if estado_id:
            filters &= Q(status=estado_id)
            
        if cuenta:
            filters_movimientos &= Q(account=cuenta)
        
        if asiento_id:
            filters &= Q(pk=asiento_id)
            
        if fecha_inicio and fecha_fin:
            filters &= Q(entry_date__range=[fecha_inicio, fecha_fin])
        elif fecha_inicio:
            filters &= Q(entry_date__gte=fecha_inicio)
        elif fecha_fin:
            filters &= Q(entry_date__lte=fecha_fin)
            
        movimientos = (AsientoMovimiento.objects.filter(filters_movimientos)
                       .select_related("account", "user_create", "user_create__person")
                       .prefetch_related(Prefetch("auxiliares", queryset=AsientoMovimientoAux.objects.filter(is_active=True))))
            
        asientos = (AsientoContable.objects.filter(filters)
                    .select_related("status", "entry_type", "period", "user_create", "user_create__person")
                    .prefetch_related(Prefetch("movimientos", queryset=movimientos))
                    .order_by("entry_number"))
        
        if asientos.count() == 1:
            return asientos.first().asiento_to_dict()
        
        return [asiento.asiento_to_dict() for asiento in asientos]
    
    
    #obtener data libro mayor
    @staticmethod
    def libro_mayor(fecha_desde=None, fecha_hasta=None, periodo_id=None, cuenta_id=None):
        #obtener periodo si es seleccionado
        periodo = None
        if periodo_id:
            periodo = PeriodoContable.objects.filter(pk=periodo_id).first()
            
            if not periodo:
                raise ValueError("El periodo no existe")
            
        #determinar fechas
        if periodo:
            if not fecha_desde:
                fecha_desde = periodo.start_date
            
            if not fecha_hasta:
                fecha_hasta = periodo.end_date
            
            #si se selecciono periodo y rango de fechas
            if fecha_desde < periodo.start_date:
                raise ValueError("La fecha desde no puede ser menor al inicio del periodo")
            
            if fecha_hasta > periodo.end_date:
                raise ValueError("La fecha hasta no puede ser mayor al final del periodo")
        
        #validar rangos de fecha
        if not fecha_desde or not fecha_hasta:
            raise ValueError("Debe indicar los rango de fechas o seleccionar un periodo contable.")
        
        if fecha_desde > fecha_hasta:
            raise ValueError("La fecha inicial no puede ser mayor a la fecha final")
        
        #filtros movimientos
        filtros_mov = {
            "is_active": True,
            "entry__is_active": True,
            "entry__is_null": False,
        }
        
        if cuenta_id:
            cuenta = Cuentas.objects.filter(pk=cuenta_id, is_active=True).first()
            
            if not cuenta:
                raise ValueError("La cuenta no existe")
            
            filtros_mov["account"] = cuenta
            
        #calcular saldo inicial
        movimientos_anteriores = AsientoMovimiento.objects.filter(**filtros_mov, entry__entry_date__lt=fecha_desde).select_related("account")
        
        saldos_iniciales = movimientos_anteriores.values("account_id", "account__cuenta_tipo", "account__tratamiento_especial").annotate(total_debe=Coalesce(Sum("debit"), 0), total_haber=Coalesce(Sum("credit"), 0))
        
        
        saldos_por_cuenta = {
            item["account_id"]: (
                item["total_debe"] - item["total_haber"] if item["cuenta_tipo"] in (1, 5) and item["tratamiento_especial"] == False else item["total_haber"] - item["total_debe"] 
            ) for item in saldos_iniciales
        }
        
        #movimientos rango de busqueda
        movimientos = (AsientoMovimiento.objects.filter(**filtros_mov, entry__entry_date__gte=fecha_desde, entry__entry_date__lte=fecha_hasta)
                       .select_related("account", "account__cuenta_tipo", "entry", "entry__status", "entry__entry_type", "entry__period", "entry__user_create", "entry__user_create__person")
                       .prefetch_related(Prefetch("auxiliares", queryset=AsientoMovimientoAux.objects.filter(is_active=True)))
                       .order_by("account__num_cuenta", "entry__entry_number", "entry__entry_date"))
        
        asientos = AsientoContable.objects.filter(is_active=True).prefetch_related(Prefetch("movimientos", queryset=movimientos)).order_by("entry_number")
        
        #agrupar por cuenta
        cuentas_data = OrderedDict()
        
        for movimiento in movimientos:
            cuenta = movimiento.account
            cuenta_id_actual = cuenta.pk
            
            if cuenta_id_actual not in cuentas_data:
                saldo_inicial = saldos_por_cuenta.get(cuenta_id_actual, 0)
                
                cuentas_data[cuenta_id_actual] = {
                    "id" : cuenta.pk,
                    "num_cuenta" : cuenta.num_cuenta,
                    "cuenta_tipo" : cuenta.cuenta_tipo.descripcion,
                    "cuenta_tipo_id" : cuenta.cuenta_tipo.id,
                    "nombre" : cuenta.nombre,
                    "saldo_inicial" : saldo_inicial,
                    "total_debe" : 0,
                    "total_haber" : 0,
                    "saldo_final" : saldo_inicial,
                    "fecha_desde" : fecha_desde,
                    "fecha_hasta" : fecha_hasta,
                    "movimientos" : []
                }
            
            cuenta_data = cuentas_data[cuenta_id_actual]
            
            #calcular saldo del movimientos
            debe = movimiento.debit or 0
            haber = movimiento.credit or 0
            
            saldo_anterior = cuenta_data["saldo_final"]
            
            saldo_actual = (saldo_anterior + debe - haber)
            
            #informacion del asiento
            asiento = movimiento.entry
            
            movimiento_data = {
                "id" : movimiento.pk,
                "fecha_asiento" : asiento.entry_date,
                "debe" : debe,
                "haber" : haber,
                "saldo_anterior" : saldo_anterior,
                "saldo" : saldo_actual,
                "glosa" : movimiento.description,
                "asiento": {
                    "id" : asiento.pk,
                    "numero_asiento" : asiento.entry_number,
                    "numero_comprobante" : asiento.voucher_number,
                    "fecha_asiento" : asiento.entry_date,
                    "glosa" : asiento.description,
                    "estado" : asiento.status.description,
                    "tipo" : asiento.entry_type.description,
                    "periodo" : {
                        "id" : asiento.period.pk,
                        "mes" : asiento.period.month,
                        "year" : asiento.period.year
                    },
                },
            }
            
            cuenta_data["movimientos"].append(movimiento_data)
            
            #actualizar totales
            cuenta_data["total_debe"] += debe
            cuenta_data["total_haber"] += haber
            cuenta_data["saldo_final"] = saldo_actual
        
        return {
            "cuentas" : list(cuentas_data.values())
        }
    
    #obtener asientos contables del periodo activo
    @staticmethod
    def asientos_periodo_activo():
        data = []
        periodo = PeriodoContableServices.get_periodo_contable_actual()
        if not periodo:
            return data
        
        movimientos = AsientoMovimiento.objects.filter(is_active=True).prefetch_related(Prefetch("auxiliares", queryset=AsientoMovimientoAux.objects.filter(is_active=True)))
        
        asientos = AsientoContable.objects.filter(period=periodo, is_active=True).prefetch_related(Prefetch("movimientos", queryset=movimientos)).order_by("entry_number")
        
        for asiento in asientos:
            data.append(asiento.asiento_to_dict())
        
        # time.sleep(10)
        return data
        
                
            
            
        
        
        
        
        
        
   

        
        