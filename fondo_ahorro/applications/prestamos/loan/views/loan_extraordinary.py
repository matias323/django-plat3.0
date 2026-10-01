import uuid
from calendar import monthrange
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import CharField, F, Prefetch, Q, Value
from django.db.models.functions import Cast, Coalesce, Concat, Trim
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models.document import Document, DocumentType
from core.models.employee import Employee
from core.models.person import Person

from ..models.loan import (
    Loan,
    LoanCollectionMethod,
    LoanExtraordinary,
    LoanInstallment,
    LoanInstallmentStatus,
    LoanRate,
    LoanStatus,
    LoanType,
    LoanTypeConcept,
)


MAX_FILE_SIZE = 10 * 1024 * 1024
MONEY = Decimal("0.01")


# ============================================================
# UTILIDADES

def _save_with_user(instance, audit_user):
    instance.save(user=audit_user)
    return instance


def _create_with_user(model, audit_user, **values):
    instance = model(**values)
    instance.save(user=audit_user)
    return instance


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def _parse_money(value):
    raw = str(value or "").strip().replace(" ", "")

    if not raw:
        raise ValueError("Debe ingresar el monto del préstamo.")

    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")

    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("El monto del préstamo no es válido.")

    if amount <= 0:
        raise ValueError("El monto del préstamo debe ser mayor a 0.")

    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


def _round_clp(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _add_months(value, months):
    month_index = value.month - 1 + int(months or 0)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _last_day_of_month(value):
    return value.replace(day=monthrange(value.year, value.month)[1])


def _extraordinary_start_date():
    today = timezone.localdate()
    next_month = _add_months(today.replace(day=1), 1)
    return next_month.replace(day=21)


def _extraordinary_end_date(start_date, term):
    return _last_day_of_month(_add_months(start_date, int(term) - 1))


def _person_name(person):
    return " ".join(
        str(value).strip()
        for value in [person.first_name, person.second_name, person.last_name_1, person.last_name_2]
        if value
    )


def _person_rut(person):
    return f"{person.rut}-{person.dv}"


def _validate_pdf(uploaded_file):
    if not uploaded_file:
        raise ValueError("Debe adjuntar el documento de autorización.")

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError("El documento no puede superar los 10 MB.")

    suffix = Path(uploaded_file.name).suffix.lower()
    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()

    if suffix != ".pdf" and content_type != "application/pdf":
        raise ValueError("El documento de autorización debe ser un PDF.")

    header = uploaded_file.read(5)
    uploaded_file.seek(0)

    if header != b"%PDF-":
        raise ValueError("El archivo seleccionado no corresponde a un PDF válido.")


def _document_type(user):
    document_type = DocumentType.objects.filter(name__iexact="Autorización Préstamo Extraordinario").first()

    if document_type:
        if not document_type.is_active:
            document_type.is_active = True
            _save_with_user(document_type, user)
        return document_type

    return _create_with_user(DocumentType, user, name="Autorización Préstamo Extraordinario")


def _save_authorization_document(request, loan, uploaded_file):
    _validate_pdf(uploaded_file)

    document_type = _document_type(request.user)
    internal_name = f"{uuid.uuid4().hex}.pdf"
    route = default_storage.save(f"loans/{loan.id}/extraordinary/{internal_name}", uploaded_file)

    try:
        document = _create_with_user(
            Document,
            request.user,
            user=request.user,
            type_document=document_type,
            ip=_get_client_ip(request),
            size=uploaded_file.size,
            document_name=uploaded_file.name,
            internal_name=internal_name,
            file_type="application/pdf",
            route=route,
        )
    except Exception:
        if default_storage.exists(route):
            default_storage.delete(route)
        raise

    return document, route


def _active_remuneration_method():
    method = (
        LoanCollectionMethod.objects
        .filter(is_active=True)
        .filter(Q(name__iexact="REMUNERACIÓN") | Q(name__iexact="REMUNERACION") | Q(name__icontains="REMUNER"))
        .order_by("id")
        .first()
    )

    if not method:
        method = LoanCollectionMethod.objects.filter(pk=1, is_active=True).first()

    if not method:
        raise ValueError("No existe un método de cobro REMUNERACIÓN activo.")

    return method


def _active_loan_status():
    status = (
        LoanStatus.objects
        .filter(is_active=True)
        .filter(Q(name__iexact="VIGENTE") | Q(name__iexact="ACTIVO"))
        .order_by("id")
        .first()
    )

    if not status:
        status = LoanStatus.objects.filter(pk=1, is_active=True).first()

    if not status:
        raise ValueError("No existe un estado VIGENTE activo para préstamos.")

    return status


def _pending_installment_status():
    status = LoanInstallmentStatus.objects.filter(is_active=True, name__iexact="PENDIENTE").first()

    if not status:
        status = LoanInstallmentStatus.objects.filter(pk=1, is_active=True).first()

    if not status:
        raise ValueError("No existe un estado PENDIENTE activo para dividendos.")

    return status


# ============================================================
# TABLA FRANCESA
def _french_schedule(principal, annual_rate, term, start_date):
    principal = Decimal(principal)
    annual_rate = Decimal(annual_rate or 0)
    term = int(term or 0)

    if principal <= 0:
        raise ValueError("El monto del préstamo debe ser mayor a 0.")
    if annual_rate < 0:
        raise ValueError("La tasa seleccionada no es válida.")
    if term <= 0:
        raise ValueError("El plazo debe ser mayor a 0.")

    monthly_float = round((1 + float(annual_rate / Decimal("100"))) ** (1 / 12) - 1, 8)
    monthly = Decimal(str(monthly_float))
    rows = []
    principal_sum = 0

    if monthly <= 0:
        payment_exact = principal / Decimal(term)
        fixed_payment = _round_clp(payment_exact)

        for number in range(1, term + 1):
            interest = 0

            if number < term:
                capital = fixed_payment
                amount = fixed_payment
            else:
                capital = _round_clp(principal - Decimal(principal_sum))
                amount = capital

            principal_sum += capital
            rows.append({
                "installment_number": number,
                "due_date": _last_day_of_month(_add_months(start_date, number - 1)),
                "amount": amount,
                "principal": capital,
                "interest": interest,
            })

        return rows

    factor = (Decimal("1") + monthly) ** term
    payment_exact = principal * monthly * factor / (factor - Decimal("1"))
    fixed_payment = _round_clp(payment_exact)
    exact_balance = principal

    for number in range(1, term + 1):
        interest_exact = exact_balance * monthly
        interest = _round_clp(interest_exact)

        if number < term:
            capital = max(fixed_payment - interest, 0)
            amount = fixed_payment
            exact_balance -= payment_exact - interest_exact
        else:
            capital = _round_clp(principal - Decimal(principal_sum))
            interest = max(fixed_payment - capital, 0)
            amount = capital + interest

        principal_sum += capital
        rows.append({
            "installment_number": number,
            "due_date": _last_day_of_month(_add_months(start_date, number - 1)),
            "amount": amount,
            "principal": capital,
            "interest": interest,
        })

    return rows


def _simulation(amount, rate, term):
    start_date = _extraordinary_start_date()
    end_date = _extraordinary_end_date(start_date, term)
    schedule = _french_schedule(amount, rate.rate, term, start_date)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "schedule": schedule,
        "interest_total": sum(row["interest"] for row in schedule),
        "installment": schedule[0]["amount"] if schedule else 0,
    }


# ============================================================
# VISTA PRINCIPAL
@login_required
@require_GET
def loan_extraordinary(request):
    loan_types = LoanType.objects.filter(is_active=True).order_by("name")
    rates = LoanRate.objects.filter(is_active=True).order_by("rate", "id")

    try:
        collection_method = _active_remuneration_method()
        loan_status = _active_loan_status()
        config_error = ""
    except ValueError as error:
        collection_method = None
        loan_status = None
        config_error = str(error)

    return render(
        request,
        "prestamos/extraordinary/loan_extraordinary.html",
        {
            "loan_types": loan_types,
            "rates": rates,
            "collection_method": collection_method,
            "loan_status": loan_status,
            "creation_date": timezone.localdate(),
            "start_date": _extraordinary_start_date(),
            "config_error": config_error,
        },
    )


# ============================================================
# BUSCAR PERSONA
@login_required
@require_GET
def extraordinary_person_search(request):
    search = str(request.GET.get("q", "") or "").strip()

    if not search:
        return JsonResponse({
            "status": "error",
            "message": "Ingrese un texto para buscar.",
            "results": [],
        }, status=400)

    employees = Employee.objects.filter(is_active=True).order_by("id")

    queryset = (
        Person.objects
        .filter(is_active=True)
        .annotate(
            rut_text=Concat(
                Cast("rut", output_field=CharField()),
                Value("-"),
                F("dv"),
                output_field=CharField(),
            )
        )
        .prefetch_related(
            Prefetch(
                "employees",
                queryset=employees,
                to_attr="active_employees",
            )
        )
    )

    # ============================================================
    # BUSQUEDA GENERAL
    # Cada palabra puede estar en cualquier parte del nombre.
    # ============================================================
    terms = [term for term in search.split() if term]

    name_query = Q()

    for term in terms:
        name_query &= (
            Q(first_name__icontains=term) |
            Q(second_name__icontains=term) |
            Q(last_name_1__icontains=term) |
            Q(last_name_2__icontains=term)
        )

    queryset = (
        queryset
        .filter(
            Q(rut_text__icontains=search) |
            Q(employees__code__icontains=search) |
            name_query
        )
        .distinct()
        .order_by("first_name", "last_name_1", "id")[:30]
    )

    results = []

    for person in queryset:
        employee = person.active_employees[0] if person.active_employees else None

        results.append({
            "id": person.id,
            "rut": _person_rut(person),
            "employee_code": employee.code if employee else "",
            "name": _person_name(person),
        })

    return JsonResponse({
        "status": "ok",
        "results": results,
    })


# ============================================================
# CONCEPTOS POR TIPO
@login_required
@require_GET
def extraordinary_concepts(request):
    try:
        loan_type_id = int(request.GET.get("loan_type_id", 0) or 0)

    except (TypeError, ValueError):
        loan_type_id = 0

    if loan_type_id <= 0:
        return JsonResponse({
            "status": "error",
            "message": "Tipo de préstamo inválido.",
            "concepts": [],
        }, status=400)

    concepts = (
        LoanTypeConcept.objects
        .filter(
            loan_type_id=loan_type_id,
            loan_type__is_active=True,
            concept__is_active=True,
            is_active=True,
        )
        .select_related(
            "loan_type",
            "concept",
        )
        .order_by(
            "concept__name",
            "id",
        )
    )

    return JsonResponse({
        "status": "ok",

        "concepts": [
            {
                "id": relation.id,
                "concept_id": relation.concept_id,
                "name": relation.concept.name,
            }
            for relation in concepts
        ],
    })


# ============================================================
# SIMULAR
@login_required
@require_POST
def extraordinary_simulate(request):
    try:
        amount = _parse_money(request.POST.get("loan_amount"))
        rate_id = int(request.POST.get("rate", 0) or 0)
        term = int(request.POST.get("term", 0) or 0)

        if term <= 0:
            raise ValueError("El plazo debe ser mayor a 0.")

        rate = LoanRate.objects.filter(pk=rate_id, is_active=True).first()

        if not rate:
            raise ValueError("Debe seleccionar una tasa válida.")

        simulation = _simulation(amount, rate, term)

        return JsonResponse({
            "status": "ok",
            "loan_amount": _round_clp(amount),
            "interest_amount": simulation["interest_total"],
            "installment": simulation["installment"],
            "term": term,
            "start_date": simulation["start_date"].isoformat(),
            "end_date": simulation["end_date"].isoformat(),
        })

    except (TypeError, ValueError) as error:
        return JsonResponse({"status": "error", "message": str(error)}, status=400)
    except Exception as error:
        return JsonResponse({"status": "error", "message": f"No se pudo simular el préstamo: {error}"}, status=500)


# ============================================================
# CREAR PRESTAMO EXTRAORDINARIO
@login_required
@require_POST
def extraordinary_create(request):
    saved_route = None

    try:
        person_id = int(request.POST.get("person_id", 0) or 0)
        loan_type_id = int(request.POST.get("loan_type", 0) or 0)
        type_concept_id = int(request.POST.get("type_concept", 0) or 0)
        rate_id = int(request.POST.get("rate", 0) or 0)
        term = int(request.POST.get("term", 0) or 0)
        amount = _parse_money(request.POST.get("loan_amount"))

        mortgage_value = str(request.POST.get("is_mortgage", "0") or "0").strip().lower()

        if mortgage_value not in {"0", "1", "false", "true", "off", "on", "no", "si", "sí"}:
            raise ValueError("El valor de hipotecario no es válido.")

        is_mortgage = mortgage_value in {"1", "true", "on", "si", "sí"}

        uploaded_file = request.FILES.get("authorization_document")
        _validate_pdf(uploaded_file)

        if person_id <= 0:
            raise ValueError("Debe seleccionar una persona.")

        if loan_type_id <= 0:
            raise ValueError("Debe seleccionar el tipo de préstamo.")

        if type_concept_id <= 0:
            raise ValueError("Debe seleccionar el concepto.")

        if rate_id <= 0:
            raise ValueError("Debe seleccionar una tasa.")

        if term <= 0:
            raise ValueError("Debe ingresar un plazo válido.")

        person = Person.objects.filter(pk=person_id, is_active=True).first()
        loan_type = LoanType.objects.filter(pk=loan_type_id, is_active=True).first()
        rate = LoanRate.objects.filter(pk=rate_id, is_active=True).first()

        if not person:
            raise ValueError("La persona seleccionada no existe o se encuentra inactiva.")

        if not loan_type:
            raise ValueError("El tipo de préstamo seleccionado no es válido.")

        if not rate:
            raise ValueError("La tasa seleccionada no es válida.")

        type_concept = (
            LoanTypeConcept.objects
            .filter(
                pk=type_concept_id,
                loan_type=loan_type,
                is_active=True,
                concept__is_active=True,
            )
            .select_related("loan_type", "concept")
            .first()
        )

        if not type_concept:
            raise ValueError("El concepto no pertenece al tipo de préstamo seleccionado.")

        collection_method = _active_remuneration_method()
        status = _active_loan_status()
        installment_status = _pending_installment_status()

        simulation = _simulation(amount, rate, term)

        with transaction.atomic():
            loan = _create_with_user(
                Loan,
                request.user,
                request=None,
                loan_type=loan_type,
                type_concept=type_concept,
                person=person,
                collection_method=collection_method,
                rate=rate,
                unique_code="",
                loan_amount=amount,
                interest_amount=simulation["interest_total"],
                principal_balance=amount,
                interest_balance=simulation["interest_total"],
                term=term,
                installments_paid=0,
                principal_paid=0,
                interest_paid=0,
                start_date=simulation["start_date"],
                end_date=simulation["end_date"],
                is_mortgage=is_mortgage,
                status=status,
                previous_loan=None,
            )

            for row in simulation["schedule"]:
                _create_with_user(
                    LoanInstallment,
                    request.user,
                    loan=loan,
                    collection_method=collection_method,
                    status=installment_status,
                    due_date=row["due_date"],
                    amount=row["amount"],
                    principal=row["principal"],
                    interest=row["interest"],
                    installment_number=row["installment_number"],
                )

            document, saved_route = _save_authorization_document(request, loan, uploaded_file)

            _create_with_user(
                LoanExtraordinary,
                request.user,
                loan=loan,
                document=document,
                ip=_get_client_ip(request),
            )

        return JsonResponse({
            "status": "ok",
            "message": "Préstamo extraordinario creado correctamente.",
            "loan_id": loan.id,
            "document_id": document.id,
        })

    except (TypeError, ValueError) as error:
        if saved_route and default_storage.exists(saved_route):
            default_storage.delete(saved_route)

        return JsonResponse({
            "status": "error",
            "message": str(error),
        }, status=400)

    except Exception as error:
        if saved_route and default_storage.exists(saved_route):
            default_storage.delete(saved_route)

        return JsonResponse({
            "status": "error",
            "message": f"No se pudo crear el préstamo extraordinario: {error}",
        }, status=500)