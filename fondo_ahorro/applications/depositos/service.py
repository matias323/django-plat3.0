from django.db import transaction
from django.db.models import Q, Prefetch, Sum, Value
from core.models.person import Person
from core.models.employee import Employee


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
            partner__is_active=True
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
                "socio":"SI" if p.partner.state == 1 else "NO",
                "ahorros":p.partner.get_ahorros()
            }
            for p in personas
        ]



