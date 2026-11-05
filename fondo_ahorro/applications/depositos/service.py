from django.db import transaction
from django.db.models import Q, Prefetch, Sum, Value, Case, F, When, IntegerField
from core.models.person import Person
from .models import Deposit, DepositApplication, ProcessType, DepositDocument
from core.models.employee import Employee
from core.models.partner import PartnerContributionType, Partner, PartnerMovement, PartnerMovementType, PartnerContribution
from core.models.document import Document, DocumentType
from applications.contabilidad.periodo_contable.services import PeriodoContableServices
from applications.contabilidad.asientos_contables.services import AsientoContableServices
from datetime import date
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from pathlib import Path
import uuid


class DepositoServices():
    
    #buscar persona tiempo real
    @staticmethod
    def search_persons(search):
        search = search.strip() 
        
        if len(search) < 2:
            return []
        
        #separamos la busqueda en caso que contenga mas de un termino
        term = search.split()
        
        #personas activas
        querysetPerson = Person.objects.filter(
            is_active=True,
            employees__is_active=True,
            # partner__is_active=True
            )

        
        #recorremos la busqueda
        for t in term:
            querysetPerson = querysetPerson.filter(
                Q(first_name__icontains=t) 
                | Q(second_name__icontains=t)
                | Q(last_name_1__icontains=t)
                | Q(last_name_2__icontains=t)
                | Q(rut__icontains=t)
                | Q(employees__code__icontains=t)
                | Q(employees__grade__name__icontains=t)
            )

        
        #aplicamos el select related
        personas = (
            querysetPerson
            .select_related("person_type", "partner")
            .prefetch_related("employees", "employees__grade")
            .distinct()
            .order_by("first_name", "last_name_1")[:10]
        )
        
        return [
            {
                "id_person": p.id,
                "rut": p.get_rut(),
                "nombre": p.get_full_name(),
                "person_type":p.person_type.description,
                "id_partner": p.partner.id if p.partner else None,
                "codigo_funcionario": p.employees.first().code if p.employees.exists() else None,
                "grado": p.employees.first().grade.name if p.employees.exists() else None,
                "grado_code": p.employees.first().grade.code if p.employees.exists() else None,
                "grado_escalafon": p.employees.first().grade.scale if p.employees.exists() else None,
                "socio":"SI" if p.partner.is_active == True else "NO",
                "ahorros":p.partner.get_ahorros()
            }
            for p in personas
        ]
        
    #registrar incremento aporte
    @staticmethod
    @transaction.atomic
    def registrar_incremento_aporte(monto, num_deposito, fecha_deposito, aporte_tipo, persona_id, socio_id, archivos_adjuntos, user, ip):
        #validar user
        if not user or not user.is_authenticated:
            raise ValueError("El usuario es requerido")
        
        #aporte
        aporte = PartnerContributionType.objects.filter(pk=aporte_tipo, is_active=True).first()
        if not aporte:
            raise ValueError("El aporte no existe")
        
        if aporte_tipo == 1:
            cuenta_aporte = 108
        elif aporte_tipo == 2:
            cuenta_aporte = 109
        else:
            cuenta_aporte = 110
        
        #socio
        socio = Partner.objects.filter(pk=socio_id, person=persona_id).first()
        if not socio:
            raise ValueError("El socio no existe")
        
        if socio.is_active == False:
            raise ValueError("La persona no es Socio!")
        
        #fecha deposito
        # convertir fecha recibida desde HTTP
        if isinstance(fecha_deposito, str):
            try:
                fecha_dep = date.fromisoformat(fecha_deposito)
            except ValueError:
                raise ValueError("La fecha del deposito no tiene un formato válido") 
        else:
            fecha_dep = fecha_deposito
            
        #verificar que fecha deposito corresponda al periodo contable activo
        periodo = PeriodoContableServices.get_periodo_contable_by_year_and_month(fecha_dep.year, fecha_dep.month)
        if not periodo or periodo.is_active == False:
            raise ValueError("No se encuentra un periodo contable activo")
        
        #verificar que no exista un deposito con el mismo numero y fecha
        existe_num = Deposit.objects.filter(deposit_number=num_deposito, deposit_date__year=fecha_dep.year, is_active=True).first()
        if existe_num:
            raise ValueError("Ya existe un deposito con el mismo numero en el año correspondiente")
        
        #registrar deposito
        deposito = Deposit.objects.create(
            deposit_date=fecha_dep,
            amount=monto,
            description=f"INCREMENTO DE APORTES - {aporte.description} - N° DEPOSITO: {num_deposito}",
            deposit_number=num_deposito,
            person=socio.person,
            voucher_number=f"DP-{num_deposito}-{fecha_dep.year}",
        )
        
        #registrar movimiento
        partner_movimiento = PartnerMovement.objects.create(
            description=f"INCREMENTO DE APORTES - {aporte.description} - N° DEPOSITO: {num_deposito}",
            amount=monto,
            contribution_type=aporte,
            partner=socio,
            movement_type=PartnerMovementType.objects.get(pk=2), #deposito
        )
        
        #registrar depositApplication
        deposito_app = DepositApplication.objects.create(
            amount=monto,
            deposit=deposito,
            description=f"INCREMENTO DE APORTES - {aporte.description} - N° DEPOSITO: {num_deposito}",
            person=socio.person,
            application=partner_movimiento,
            process_type=ProcessType.objects.get(pk=2), #incremento aportes
            employee_grade=socio.person.employees.first().grade,
        )
        
        #obtener socio aporte
        partner_aporte = PartnerContribution.objects.select_for_update().filter(partner=socio, contribution_type=aporte).first()
        if not partner_aporte:
            raise ValueError("El socio no tiene un aporte registrado")
        
        #incrementar aporte
        partner_aporte.amount += monto
        partner_aporte.save()
        
        #registrar asiento contable
        AsientoContableServices.crear_asiento_completo(
            user=user,
            entry_date=fecha_dep,
            description=f"INCREMENTO DE APORTES - {aporte.description} - N° DEPOSITO: {num_deposito}",
            entry_type=1, #ingreso
            movimientos=[
                {
                    "account": 13, #banco
                    "description": f"INCREMENTO DE APORTES - {aporte.description} - N° DEPOSITO: {num_deposito}",
                    "debit": monto,
                    "credit": 0
                },
                {
                    "account": cuenta_aporte, #cuenta aporte(108=A1, 109=A2, 110=A3)
                    "description": f"INCREMENTO DE APORTES - {aporte.description} - N° DEPOSITO: {num_deposito}",
                    "debit": 0,
                    "credit": monto,
                    "auxiliares": [
                        {
                            "person": socio.person.id,
                            "amount": monto
                        }
                    ]
                }
            ],
            origen=deposito_app,
        )
        
        #guardar y registrar documentos
        for archivo in archivos_adjuntos:
            DepositoServices.save_document(archivo, ip, user, deposito)
            
        
        return deposito
    
    
    #guardar documento
    def save_document(archivo, ip, user, deposito):
        document_type = DocumentType.objects.filter(name__iexact="COMPROBANTE DEPOSITO").first()
        #guardar archivo
        internal_name = uuid.uuid4().hex
        extension = Path(archivo.name).suffix.lower()
        relative_path = f"deposits/{internal_name}{extension}"
        saved_path = default_storage.save(relative_path, archivo)
        
        #registrar archivo
        documento = Document.objects.create(
            type_document=document_type,#comprobante deposito
            ip=ip,
            size=archivo.size,
            document_name=archivo.name,
            internal_name=internal_name,
            file_type=archivo.content_type or "application/pdf",
            route=saved_path,
            user=user
        )
        
        #registrar documento deposito
        DepositDocument.objects.create(
            deposit=deposito,
            document=documento,
        )
        
    #buscar deposito
    def search_deposito(
        deposit_pk=None, 
        deposit_number=None, 
        query=None, 
        tipoProceso=None, 
        fecha_inicio=None, 
        fecha_fin=None, 
        montoMin=None, 
        montoMax=None, 
        person_pk=None,
        deposit_app_pk=None):
        
        filters = Q(is_active=True)
        filters_app = Q(is_active=True)
        
        if deposit_pk:
            filters &= Q(pk=deposit_pk)
        
        if tipoProceso:
            filters &= Q(applications__process_type_id=tipoProceso)
            
        if query:
            terms = query.split()
            query_filters = Q()
            
            for t in terms:
                # Para cada término, evaluamos si coincide en CUALQUIERA de los campos (OR)
                term_q = (
                    Q(deposit_number__icontains=t) |
                    Q(person__first_name__icontains=t) |
                    Q(person__second_name__icontains=t) |
                    Q(person__last_name_1__icontains=t) |
                    Q(person__last_name_2__icontains=t) |
                    Q(person__rut__icontains=t) |
                    Q(person__employees__code__icontains=t)
                )
                # Entre diferentes palabras exigimos que se cumplan (AND)
                query_filters &= term_q
                
            filters &= query_filters
            
        if montoMin:
            filters &= Q(amount__gte=montoMin)
            
        if montoMax:
            filters &= Q(amount__lte=montoMax)
            
        if deposit_number:
            filters &= Q(deposit_number=deposit_number)
            
        if fecha_inicio and fecha_fin:
            filters &= Q(deposit_date__range=[fecha_inicio, fecha_fin])
            
        elif fecha_inicio:
            filters &= Q(deposit_date__gte=fecha_inicio)
            
        elif fecha_fin:
            filters &= Q(deposit_date__lte=fecha_fin)
            
        if person_pk:
            filters &= Q(person=person_pk)
        
        if deposit_app_pk:
            filters &= Q(applications__pk=deposit_app_pk)
            filters_app &= Q(pk=deposit_app_pk)
            
        deposit_documents = (DepositDocument.objects.filter(is_active=True).select_related("document"))
            
        deposit_app = (DepositApplication.objects.filter(filters_app)
                        .select_related("user_create", "user_create__person", "process_type", "person", "application_content_type")
                        .distinct())
            
        depositos = (Deposit.objects.filter(filters)
                    .select_related("user_create", "user_create__person", "person")
                    .prefetch_related(Prefetch("documents", queryset=deposit_documents))
                    .prefetch_related(Prefetch("applications", queryset=deposit_app))
                    .order_by("deposit_number"))

        # if depositos.count() == 1:
        #     return depositos.first().deposit_to_dic()
        
        return [deposito.deposit_to_dic() for deposito in depositos]
    
    
    #buscar movimeintos
    def search_movimientos(anio = None, tipo = None, cuenta = None, persona_pk = None):
        filters = Q(is_active=True)
        
        if anio:
            filters &= Q(created_at__year=anio)
            
        if tipo:
            filters &= Q(movement_type=tipo)
            
        if cuenta:
            filters &= Q(contribution_type=cuenta)
            
        if persona_pk:
            filters &= Q(partner__person=persona_pk)
            
        movimientos = PartnerMovement.objects.filter(filters).order_by("created_at")
        
        return [movimiento.to_dict() for movimiento in movimientos]
    
    #saldo de socio anio
    def saldo_anio(persona_pk, anio, cuenta = None, tipo = None):
        fecha_inicio = date(anio, 1, 1)
        fecha_fin = date(anio, 12, 31)

        # 1. Obtenemos los montos actuales de forma segura
        contribuciones = PartnerContribution.objects.filter(
            partner__person=persona_pk, contribution_type__in=[1, 2, 3]
        ).values("contribution_type", "amount")

        contri_dict = {c["contribution_type"]: int(c["amount"]) for c in contribuciones}
        a1_inicio = int(contri_dict.get(1, 0))
        a2_inicio = int(contri_dict.get(2, 0))
        a3_inicio = int(contri_dict.get(3, 0))


        # 2. Filtro base para los movimientos posteriores a la fecha
        filters = Q(is_active=True) & Q(partner__person=persona_pk) & Q(created_at__date__gte=fecha_inicio)
        

        # 3. Agregación inteligente considerando los tipos de movimientos (Giros, Depósitos, etc.)
        # Aquí ajustas la condición de acuerdo a cómo guardas los giros y depósitos en tu BD.
        # Por ejemplo: Si movement_type == 1 es Depósito (suma) y movement_type == 2 es Giro (resta).
        movimientos_agregados = (
            PartnerMovement.objects.filter(filters)
            .values("contribution_type")
            .annotate(
                neto=Sum(
                    Case(
                        # giro
                        When(movement_type=1, then=F("amount")),
                        # depositos
                        When(movement_type__gt=1, then=-F("amount")),
                        # Por defecto por si hay otro tipo
                        default=0,
                        output_field=IntegerField(),
                    ),
                    output_field=IntegerField(),
                )
            )
        )

        mov_dict = {m["contribution_type"]: (m["neto"] or 0) for m in movimientos_agregados}

        neto_a1 = mov_dict.get(1, 0)
        neto_a2 = mov_dict.get(2, 0)
        neto_a3 = mov_dict.get(3, 0)

        # Como estamos calculando hacia atrás (saldo inicial),
        # al saldo actual le "deshacemos" el efecto de los movimientos posteriores:
        # Si un depósito sumó, para ir al pasado se resta; si un giro restó, para ir al pasado se suma.
        a1_inicio += neto_a1
        a2_inicio += neto_a2
        a3_inicio += neto_a3
        saldo_inicio = a1_inicio + a2_inicio + a3_inicio
        
        a1_final = a1_inicio
        a2_final = a2_inicio
        a3_final = a3_inicio
        
        #buscar movimientos dentro del periodo de busqueda para obtenr el saldo final del periodo de busqueda
        filters &= Q(created_at__date__lte=fecha_fin)
        print(fecha_fin)
        
        if cuenta:
            filters &= Q(contribution_type=cuenta)
        
        if tipo:
            filters &= Q(movement_type=tipo)
        
        movimientos_agregados_fin = (
                    PartnerMovement.objects.filter(filters)
                    .values("contribution_type")
                    .annotate(
                        neto=Sum(
                            Case(
                                # giro
                                When(movement_type=1, then=-F("amount")),
                                # depositos
                                When(movement_type__gt=1, then=F("amount")),
                                # Por defecto por si hay otro tipo
                                default=0,
                                output_field=IntegerField(),
                            ),
                            output_field=IntegerField(),
                        )
                    )
                )
        
        mov_dict_fin = {m["contribution_type"]: (m["neto"] or 0) for m in movimientos_agregados_fin}
        
        neto_a1_fin = mov_dict_fin.get(1, 0)
        neto_a2_fin = mov_dict_fin.get(2, 0)
        neto_a3_fin = mov_dict_fin.get(3, 0)
        
        a1_final += neto_a1_fin
        a2_final += neto_a2_fin
        a3_final += neto_a3_fin
        saldo_final = a1_final + a2_final + a3_final
        
        

        return {
            "a1_final": a1_final,
            "a2_final": a2_final,
            "a3_final": a3_final,
            "saldo_final": saldo_final,
            "saldo_inicio": saldo_inicio,
            "a1_inicio": a1_inicio,
            "a2_inicio": a2_inicio,
            "a3_inicio": a3_inicio,
        }
        
        # fecha_inicio = date(anio+1, 1, 1)
        
        # filters = Q(is_active=True)
        # filters &= Q(partner__person=persona_pk)
        # filters &= Q(created_at__gte=fecha_inicio)
        
        # movimientos = PartnerMovement.objects.filter(filters).select_related("contribution_type", "contribution_type")
        
        # a1_actual = int(PartnerContribution.objects.get(partner__person=persona_pk, contribution_type_id=1).amount)
        # a2_actual = int(PartnerContribution.objects.get(partner__person=persona_pk, contribution_type_id=2).amount)
        # a3_actual = int(PartnerContribution.objects.get(partner__person=persona_pk, contribution_type_id=3).amount)
        
        # saldo_inicio = a1_actual + a2_actual + a3_actual
        # a1_inicio = a1_actual
        # a2_inicio = a2_actual
        # a3_inicio = a3_actual
        # for movimiento in movimientos:
        #     if movimiento.contribution_type == 1: #a1
        #         a1_inicio += (
        #                 movimiento.amount if movimiento.movement_type_id == 1 else -movimiento.amount
        #             )
        #     elif movimiento.contribution_type == 2: #a2
        #         a2_inicio += (
        #                 movimiento.amount if movimiento.movement_type_id == 1 else -movimiento.amount
        #             )
        #     elif movimiento.contribution_type == 3: #a3
        #         a3_inicio += (
        #                 movimiento.amount if movimiento.movement_type_id == 1 else -movimiento.amount
        #             )
            
        #     saldo_inicio += movimiento.amount if movimiento.movement_type_id == 1 else -movimiento.amount
            
        # return [
        #     {
        #         "a1_actual": a1_actual,
        #         "a2_actual": a2_actual,
        #         "a3_actual": a3_actual,
        #         "saldo_actual": a1_actual + a2_actual + a3_actual,
        #         "saldo_inicio": saldo_inicio,
        #         "a1_inicio": a1_inicio,
        #         "a2_inicio": a2_inicio,
        #         "a3_inicio": a3_inicio
        #     }
        # ]
        
            
        
    
    

        
        
        
    

        
        
        
        
        
        
        
        
        



