import re
import uuid
from calendar import monthrange
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import CharField, F, Prefetch, Q, Value
from django.db.models.functions import Cast, Concat
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from core.models.document import Document
from core.models.employee import Employee
from core.models.person import Person
from core.models.observation import Observation
from core.models.request import Request, RequestStatus, RequestType

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from applications.prestamos.loan.models.loan import (
    Loan,
    LoanCollectionMethod,
    LoanInstallment,
    LoanInstallmentStatus,
    LoanRate,
    LoanStatus,
    LoanType,
    LoanTypeConcept,
)

from .models import (
    RequestLoan,
    RequestLoanDocument,
    RequestLoanDocumentRequirement,
    RequestLoanObservation,
    RequestLoanRequiredDocument,
    RequestLoanState,
)


REQUEST_TYPE_LOAN = "Loan"
REQUEST_STATUS_ENTERED = "INGRESADO"
REQUEST_STATUS_APPROVED = "APROBADO"
REQUEST_STATUS_REJECTED = "RECHAZADO"
REQUEST_STATUS_PAID = "PAGADO"

REQUEST_LOAN_STATE_ENTERED = "ENTERED"
REQUEST_LOAN_STATE_LEGAL = "LEGAL_AREA"
REQUEST_LOAN_STATE_COUNCIL_WAIT = "COUNCIL_WAIT"
REQUEST_LOAN_STATE_COUNCIL_APPROVED = "COUNCIL_APPROVED"
REQUEST_LOAN_STATE_COUNCIL_APPROVED_MODIFIED = "COUNCIL_APPROVED_MODIFIED"
REQUEST_LOAN_STATE_PAID = "PAID"

DEFAULT_REQUEST_LOAN_STATES = (
    {"code": REQUEST_LOAN_STATE_ENTERED, "name": "Ingresado", "sequence": 1, "is_approval_state": False, "is_paid_state": False},
    {"code": REQUEST_LOAN_STATE_LEGAL, "name": "Área Legal", "sequence": 2, "is_approval_state": False, "is_paid_state": False},
    {"code": REQUEST_LOAN_STATE_COUNCIL_WAIT, "name": "Espera Consejo", "sequence": 3, "is_approval_state": False, "is_paid_state": False},
    {"code": REQUEST_LOAN_STATE_COUNCIL_APPROVED, "name": "Aprobado Consejo", "sequence": 4, "is_approval_state": True, "is_paid_state": False},
    {"code": REQUEST_LOAN_STATE_COUNCIL_APPROVED_MODIFIED, "name": "Aprobado Consejo con Modificaciones", "sequence": 4, "is_approval_state": True, "is_paid_state": False},
    {"code": REQUEST_LOAN_STATE_PAID, "name": "Pagado", "sequence": 5, "is_approval_state": False, "is_paid_state": True},
)

MAX_FILE_SIZE = 10 * 1024 * 1024


# ============================================================
# HELPERS
# ============================================================
def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def _normalize_spaces(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def _person_full_name(person):
    return " ".join(
        value
        for value in [
            person.first_name,
            person.second_name,
            person.last_name_1,
            person.last_name_2,
        ]
        if value
    )


def _format_rut(person):
    rut = str(person.rut or "")
    formatted = ""

    while rut:
        if formatted:
            formatted = f"{rut[-3:]}.{formatted}"
        else:
            formatted = rut[-3:]
        rut = rut[:-3]

    return f"{formatted}-{person.dv}"


def _save_with_user(instance, user, update_fields=None):
    if update_fields:
        fields = list(update_fields)

        if "updated_at" not in fields:
            fields.append("updated_at")

        if "user_update" not in fields:
            fields.append("user_update")

        instance.save(user=user, update_fields=fields)
        return instance

    instance.save(user=user)
    return instance


def _get_or_create_request_type(user):
    request_type = RequestType.objects.filter(name__iexact=REQUEST_TYPE_LOAN).first()

    if request_type:
        return request_type

    request_type = RequestType(name=REQUEST_TYPE_LOAN)
    return _save_with_user(request_type, user)


def _get_or_create_request_status(name, user):
    status = RequestStatus.objects.filter(status_type__iexact=name).first()

    if status:
        return status

    status = RequestStatus(status_type=name)
    return _save_with_user(status, user)


def _create_observation(request, request_loan, action, comment):
    observation = Observation(
        comment=comment,
        user=request.user,
        time=timezone.localtime().time(),
        ip=_get_client_ip(request),
    )
    _save_with_user(observation, request.user)

    relation = RequestLoanObservation(
        request_loan=request_loan,
        observation=observation,
        action=action,
    )
    _save_with_user(relation, request.user)

    return relation


def _validate_pdf(uploaded_file):
    if not uploaded_file:
        raise ValueError("Debe adjuntar un archivo PDF.")

    extension = Path(uploaded_file.name).suffix.lower()

    if extension != ".pdf":
        raise ValueError("El documento debe estar en formato PDF.")

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError("El documento supera el tamaño máximo permitido de 10 MB.")


def _ensure_request_loan_states(user):
    states = []

    for config in DEFAULT_REQUEST_LOAN_STATES:
        state = RequestLoanState.objects.filter(code=config["code"]).first()

        if not state:
            state = RequestLoanState(**config)
            _save_with_user(state, user)
        else:
            changed = []

            for field in ["name", "sequence", "is_approval_state", "is_paid_state"]:
                if getattr(state, field) != config[field]:
                    setattr(state, field, config[field])
                    changed.append(field)

            if not state.is_active:
                state.is_active = True
                changed.append("is_active")

            if changed:
                _save_with_user(state, user, changed)

        states.append(state)

    return states


def _entered_request_loan_state(user):
    _ensure_request_loan_states(user)

    return RequestLoanState.objects.get(
        code=REQUEST_LOAN_STATE_ENTERED,
        is_active=True,
    )


def _assign_default_request_loan_state(request_loan, user):
    if request_loan.state_id:
        return request_loan.state

    state = _entered_request_loan_state(user)
    request_loan.state = state
    _save_with_user(request_loan, user, ["state"])
    return state


def _request_is_rejected(request_loan):
    status = _normalize_spaces(request_loan.request.status.status_type).upper()
    return status == REQUEST_STATUS_REJECTED


def _request_is_final(request_loan):
    if _request_is_rejected(request_loan):
        return True

    return bool(request_loan.state and request_loan.state.is_paid_state)


def _latest_document(required_document):
    return required_document.documents.select_related(
        "document",
        "document__type_document",
        "validated_by",
    ).order_by("-id").first()


def _approval_branch_name(request_loan):
    if request_loan.state and request_loan.state.is_approval_state:
        return request_loan.state.name

    state_change = (
        request_loan.observations
        .filter(is_active=True, action=RequestLoanObservation.Action.STATE_CHANGED)
        .select_related("observation")
        .order_by("-id")
        .first()
    )

    if not state_change or not state_change.observation:
        return "Aprobación Consejo"

    comment = state_change.observation.comment or ""
    marker = "Estado anterior:"

    if marker not in comment:
        return "Aprobación Consejo"

    previous_name = comment.split(marker, 1)[1].split(".", 1)[0].strip()
    approval_names = set(
        RequestLoanState.objects.filter(
            is_active=True,
            is_approval_state=True,
        ).values_list("name", flat=True)
    )

    return previous_name if previous_name in approval_names else "Aprobación Consejo"


def _request_timeline(request_loan):
    states = list(
        RequestLoanState.objects
        .filter(is_active=True)
        .order_by("sequence", "id")
    )

    if not states:
        return []

    current_state = request_loan.state
    current_sequence = current_state.sequence if current_state else states[0].sequence
    rejected = _request_is_rejected(request_loan)

    groups = {}
    for state in states:
        groups.setdefault(state.sequence, []).append(state)

    result = []

    for sequence in sorted(groups):
        group = groups[sequence]

        if len(group) == 1:
            label = group[0].name
        elif current_state and current_state.sequence == sequence:
            label = current_state.name
        elif current_sequence > sequence:
            label = _approval_branch_name(request_loan)
        else:
            label = "Aprobación Consejo"

        state_value = "future"

        if sequence < current_sequence:
            state_value = "done"
        elif sequence == current_sequence:
            if rejected:
                state_value = "rejected"
                label = "Rechazado"
            elif current_state and current_state.is_paid_state:
                state_value = "done"
            else:
                state_value = "current"

        result.append({
            "sequence": sequence,
            "label": label,
            "state": state_value,
        })

    return result



def _request_data_can_be_edited(request_loan):
    # Si está rechazado, no se modifica
    if _request_is_rejected(request_loan):
        return False

    # Si no tiene estado (por error de datos), no se modifica
    if not request_loan.state_id:
        return False

    # Si la solicitud ya está pagada, no se modifica
    if request_loan.state.is_paid_state:
        return True

    # Para el resto de casos (por ahora), si se permite modificar
    return True


def _sync_existing_loan_from_request(request, request_loan, loan):
    """
    Sincroniza el préstamo ya creado cuando una solicitud en
    'Aprobado Consejo con Modificaciones' cambia sus datos.
    Recalcula la tabla francesa y vuelve a generar los dividendos.
    """
    rate = loan.rate or _default_loan_rate()
    collection_method = loan.collection_method or _default_collection_method()
    installment_status = _default_installment_status()

    amount = Decimal(request_loan.loan_amount)
    term = int(request_loan.term)
    simulation = _loan_simulation(
        amount,
        rate,
        term,
    )

    loan.loan_type = request_loan.loan_type
    loan.type_concept = request_loan.type_concept
    loan.person = request_loan.employee.person
    loan.loan_amount = amount
    loan.interest_amount = simulation["interest_total"]
    loan.principal_balance = amount
    loan.interest_balance = simulation["interest_total"]
    loan.term = term
    loan.installments_paid = 0
    loan.principal_paid = 0
    loan.interest_paid = 0
    loan.start_date = simulation["start_date"]
    loan.end_date = simulation["end_date"]

    _save_with_user(
        loan,
        request.user,
        [
            "loan_type",
            "type_concept",
            "person",
            "loan_amount",
            "interest_amount",
            "principal_balance",
            "interest_balance",
            "term",
            "installments_paid",
            "principal_paid",
            "interest_paid",
            "start_date",
            "end_date",
        ],
    )

    # Los dividendos existentes corresponden a los valores anteriores.
    # Se recrean completamente con los nuevos datos aprobados.
    LoanInstallment.objects.filter(
        loan=loan,
    ).delete()

    for row in simulation["schedule"]:
        installment = LoanInstallment(
            loan=loan,
            collection_method=collection_method,
            status=installment_status,
            due_date=row["due_date"],
            amount=row["amount"],
            principal=row["principal"],
            interest=row["interest"],
            installment_number=row["installment_number"],
        )
        _save_with_user(
            installment,
            request.user,
        )

    return loan


def _next_request_loan_states(request_loan):
    """
    Devuelve únicamente los estados permitidos desde el estado actual.

    Flujo:
    Ingresado -> Área Legal
    Área Legal -> Espera Consejo
    Espera Consejo -> Aprobado Consejo / Aprobado Consejo con Modificaciones
    Cualquier aprobación -> Pagado
    Pagado -> sin opciones
    """
    if not request_loan.state_id:
        return RequestLoanState.objects.none()

    current_state = request_loan.state

    if current_state.is_paid_state:
        return RequestLoanState.objects.none()

    # Desde un estado de aprobación, solo se puede avanzar a Pagado.
    if current_state.is_approval_state:
        return (
            RequestLoanState.objects
            .filter(
                is_active=True,
                is_paid_state=True,
            )
            .order_by("sequence", "id")
        )

    # Para el resto, solo se permite avanzar al nivel inmediatamente siguiente.
    next_sequence = (
        RequestLoanState.objects
        .filter(
            is_active=True,
            sequence__gt=current_state.sequence,
        )
        .order_by("sequence")
        .values_list("sequence", flat=True)
        .first()
    )

    if next_sequence is None:
        return RequestLoanState.objects.none()

    return (
        RequestLoanState.objects
        .filter(
            is_active=True,
            sequence=next_sequence,
        )
        .order_by("id")
    )


# ============================================================
# CONFIGURACION FIJA PARA PRESTAMOS CREADOS DESDE SOLICITUD
# ============================================================
DEFAULT_LOAN_RATE_ID = 1
DEFAULT_COLLECTION_METHOD_ID = 1
DEFAULT_LOAN_STATUS_ID = 1
DEFAULT_INSTALLMENT_STATUS_ID = 1


def _default_loan_rate():
    rate = LoanRate.objects.filter(pk=DEFAULT_LOAN_RATE_ID, is_active=True).first()
    if not rate:
        raise ValueError(f"No existe una tasa activa con ID {DEFAULT_LOAN_RATE_ID}.")
    return rate


def _default_collection_method():
    collection_method = LoanCollectionMethod.objects.filter(pk=DEFAULT_COLLECTION_METHOD_ID, is_active=True).first()
    if not collection_method:
        raise ValueError(f"No existe un método de cobro activo con ID {DEFAULT_COLLECTION_METHOD_ID}.")
    return collection_method


def _default_loan_status():
    status = LoanStatus.objects.filter(pk=DEFAULT_LOAN_STATUS_ID, is_active=True).first()
    if not status:
        raise ValueError(f"No existe un estado de préstamo activo con ID {DEFAULT_LOAN_STATUS_ID}.")
    return status


def _default_installment_status():
    status = LoanInstallmentStatus.objects.filter(pk=DEFAULT_INSTALLMENT_STATUS_ID, is_active=True).first()
    if not status:
        raise ValueError(f"No existe un estado de dividendo activo con ID {DEFAULT_INSTALLMENT_STATUS_ID}.")
    return status


# ============================================================
# TABLA FRANCESA
# Misma lógica utilizada por préstamos extraordinarios.
# ============================================================
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


def _loan_start_date():
    today = timezone.localdate()
    next_month = _add_months(today.replace(day=1), 1)
    return next_month.replace(day=21)


def _loan_end_date(start_date, term):
    return _last_day_of_month(_add_months(start_date, int(term) - 1))


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


def _loan_simulation(amount, rate, term):
    start_date = _loan_start_date()
    end_date = _loan_end_date(start_date, term)
    schedule = _french_schedule(amount, rate.rate, term, start_date)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "schedule": schedule,
        "interest_total": sum(row["interest"] for row in schedule),
        "installment": schedule[0]["amount"] if schedule else 0,
    }


def _create_loan_from_request(request, request_loan):
    existing_loan = Loan.objects.filter(
        request=request_loan.request
    ).order_by("id").first()

    if existing_loan:
        return existing_loan, False

    rate = _default_loan_rate()
    collection_method = _default_collection_method()
    loan_status = _default_loan_status()
    installment_status = _default_installment_status()

    amount = Decimal(request_loan.loan_amount)
    term = int(request_loan.term)
    simulation = _loan_simulation(amount, rate, term)

    loan = Loan(
        request=request_loan.request,
        loan_type=request_loan.loan_type,
        type_concept=request_loan.type_concept,
        person=request_loan.employee.person,
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
        is_mortgage=False,
        status=loan_status,
        previous_loan=None,
    )
    _save_with_user(loan, request.user)

    for row in simulation["schedule"]:
        installment = LoanInstallment(
            loan=loan,
            collection_method=collection_method,
            status=installment_status,
            due_date=row["due_date"],
            amount=row["amount"],
            principal=row["principal"],
            interest=row["interest"],
            installment_number=row["installment_number"],
        )
        _save_with_user(installment, request.user)

    return loan, True


# ============================================================
# LISTADO
# ============================================================
@login_required
def request_loan_list(request):
    return render(request, "prestamos/loan_requests/request_loan_list.html")


@login_required
@require_GET
def request_loan_datatable(request):
    try:
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
    except (TypeError, ValueError):
        draw, start, length = 1, 0, 10

    _ensure_request_loan_states(request.user)
    entered_state = _entered_request_loan_state(request.user)
    search = _normalize_spaces(request.GET.get("search[value]", ""))

    queryset = (
        RequestLoan.objects
        .select_related(
            "request",
            "request__status",
            "request__request_type",
            "state",
            "employee",
            "employee__person",
            "employee__grade",
            "loan_type",
            "type_concept",
            "type_concept__concept",
        )
        .filter(
            is_active=True
        )
        .order_by("-id")
    )

    records_total = queryset.count()

    if search:
        tokens = [token for token in search.split(" ") if token]

        for token in tokens:
            q = (
                Q(employee__code__icontains=token)
                | Q(employee__person__first_name__icontains=token)
                | Q(employee__person__second_name__icontains=token)
                | Q(employee__person__last_name_1__icontains=token)
                | Q(employee__person__last_name_2__icontains=token)
                | Q(loan_type__name__icontains=token)
                | Q(type_concept__concept__name__icontains=token)
                | Q(state__name__icontains=token)
                | Q(request__status__status_type__icontains=token)
            )

            digits = re.sub(r"[^0-9]", "", token)

            if digits:
                try:
                    q |= Q(employee__person__rut=int(digits))
                except ValueError:
                    pass

            queryset = queryset.filter(q)

    records_filtered = queryset.count()
    rows = queryset[start:start + length]
    data = []

    for item in rows:
        person = item.employee.person

        data.append({
            "id": item.id,
            "employee_code": item.employee.code,
            "rut": _format_rut(person),
            "name": _person_full_name(person),
            "grade": str(item.employee.grade) if getattr(item.employee, "grade", None) else "",
            "loan_type": item.loan_type.name if item.loan_type else "",
            "concept": item.type_concept.concept.name if item.type_concept else "",
            "loan_amount": float(item.loan_amount or 0),
            "term": item.term,
            "request_date": item.request_date.strftime("%d-%m-%Y"),

            # se envía nombre real y no solo el texto hardcodeado, adjuntamos los boolean para que el front tome desición de diseño (color)
            "status_name": ("Rechazado" if _request_is_rejected(item) else (item.state.name if item.state else entered_state.name)),
            "is_rejected": _request_is_rejected(item),
            "is_approval_state": item.state.is_approval_state if item.state else False,
            "is_paid_state": item.state.is_paid_state if item.state else False,

            "detail_url": reverse("loan_requests:detail", args=[item.id]),
            "detail_modal_url": reverse("loan_requests:detail_modal", args=[item.id]),
        })

    return JsonResponse({
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": data,
    })

# ============================================================
# BUSCAR FUNCIONARIO
# Misma lógica utilizada en préstamos extraordinarios:
# nombre en cualquier orden, RUT o código de funcionario.
# ============================================================
@login_required
@require_GET
def employee_search(request):
    try:
        search = str(request.GET.get("q", "") or "").strip()

        if not search:
            return JsonResponse({
                "status": "error",
                "message": "Ingrese un texto para buscar.",
                "results": [],
            }, status=400)

        employees = (
            Employee.objects
            .filter(is_active=True)
            .select_related("grade")
            .order_by("id")
        )

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
                Prefetch("employees", queryset=employees, to_attr="active_employees")
            )
        )

        terms = [term for term in search.split() if term]
        name_query = Q()

        for term in terms:
            name_query &= (
                Q(first_name__icontains=term)
                | Q(second_name__icontains=term)
                | Q(last_name_1__icontains=term)
                | Q(last_name_2__icontains=term)
            )

        queryset = (
            queryset
            .filter(
                Q(rut_text__icontains=search)
                | Q(employees__code__icontains=search)
                | name_query
            )
            .distinct()
            .order_by("first_name", "last_name_1", "id")[:30]
        )

        results = []

        for person in queryset:
            employee = person.active_employees[0] if person.active_employees else None

            if not employee:
                continue

            results.append({
                "id": employee.id,
                "person_id": person.id,
                "rut": _format_rut(person),
                "code": employee.code or "",
                "name": _person_full_name(person),
                "grade": str(employee.grade) if employee.grade else "",
            })

        return JsonResponse({"status": "ok", "results": results})

    except Exception as error:
        return JsonResponse({
            "status": "error",
            "message": str(error),
            "results": [],
        }, status=500)

# ============================================================
# CREAR SOLICITUD
# ============================================================
@login_required
def request_loan_create(request):
    _ensure_request_loan_states(request.user)
    entered_loan_state = _entered_request_loan_state(request.user)
    loan_types = LoanType.objects.filter(is_active=True).order_by("name", "id")
    requirements = (
        RequestLoanDocumentRequirement.objects
        .filter(is_active=True)
        .select_related("document_type")
        .order_by("id")
    )

    context = {
        "loan_types": loan_types,
        "requirements": requirements,
        "request_date": timezone.localdate(),
        "form_data": {},
        "selected_employee": None,
    }

    if request.method == "GET":
        return render(
            request,
            "prestamos/loan_requests/request_loan_form.html",
            context,
        )

    is_app_request = request.headers.get("X-App-Request") == "true"

    def fail(message, status=400):
        if is_app_request:
            return JsonResponse({
                "status": "error",
                "message": message,
            }, status=status)

        messages.error(request, message)
        context["form_data"] = request.POST
        return render(
            request,
            "prestamos/loan_requests/request_loan_form.html",
            context,
            status=status,
        )

    employee_id = request.POST.get("employee_id")
    loan_type_id = request.POST.get("loan_type")
    type_concept_id = request.POST.get("type_concept")
    loan_amount_raw = str(request.POST.get("loan_amount", "") or "").strip()
    term_raw = str(request.POST.get("term", "") or "").strip()
    request_date = request.POST.get("request_date")

    context["form_data"] = request.POST

    if not employee_id:
        return fail("Debe seleccionar un funcionario.")

    employee = (
        Employee.objects
        .select_related("person", "grade")
        .filter(pk=employee_id, is_active=True)
        .first()
    )

    if not employee:
        return fail("El funcionario seleccionado no existe o se encuentra inactivo.")

    context["selected_employee"] = {
        "id": employee.id,
        "code": employee.code or "",
        "rut": _format_rut(employee.person),
        "name": _person_full_name(employee.person),
        "grade": str(employee.grade) if employee.grade else "",
    }

    if not loan_type_id:
        return fail("Debe seleccionar un tipo de préstamo.")

    loan_type = LoanType.objects.filter(
        pk=loan_type_id,
        is_active=True,
    ).first()

    if not loan_type:
        return fail("El tipo de préstamo seleccionado no es válido.")

    if not type_concept_id:
        return fail("Debe seleccionar un concepto de préstamo.")

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
        return fail("El concepto seleccionado no corresponde al tipo de préstamo.")

    if not loan_amount_raw:
        return fail("Debe ingresar el monto solicitado.")

    try:
        loan_amount = Decimal(loan_amount_raw)
    except (InvalidOperation, TypeError, ValueError):
        return fail("El monto solicitado no es válido.")

    if loan_amount <= 0:
        return fail("El monto solicitado debe ser mayor a cero.")

    try:
        term = int(term_raw)
    except (TypeError, ValueError):
        term = 0

    if term <= 0:
        return fail("Debe ingresar un plazo válido.")

    if not request_date:
        return fail("Debe ingresar la fecha de la solicitud.")

    requirements = list(
        RequestLoanDocumentRequirement.objects
        .filter(is_active=True)
        .select_related("document_type")
        .order_by("id")
    )
    context["requirements"] = requirements

    if not requirements:
        return fail(
            "No existen documentos requeridos configurados para solicitudes de préstamo."
        )

    saved_paths = []

    try:
        with transaction.atomic():
            request_type = _get_or_create_request_type(request.user)
            entered_status = _get_or_create_request_status(
                REQUEST_STATUS_ENTERED,
                request.user,
            )

            core_request = Request(
                request_type=request_type,
                status=entered_status,
            )
            _save_with_user(core_request, request.user)

            request_loan = RequestLoan(
                request=core_request,
                state=entered_loan_state,
                employee=employee,
                loan_type=loan_type,
                type_concept=type_concept,
                loan_amount=loan_amount,
                term=term,
                request_date=request_date,
            )
            _save_with_user(request_loan, request.user)

            # Se crean TODOS los requisitos documentales aunque todavía no
            # exista archivo. Esto permite ir adjuntándolos posteriormente.
            for requirement in requirements:
                required_document = RequestLoanRequiredDocument(
                    request_loan=request_loan,
                    document_type=requirement.document_type,
                )
                _save_with_user(required_document, request.user)

                uploaded_file = request.FILES.get(
                    f"document_{requirement.id}"
                )

                # El archivo NO es obligatorio al crear la solicitud.
                if not uploaded_file:
                    continue

                _validate_pdf(uploaded_file)

                extension = Path(uploaded_file.name).suffix.lower()
                internal_name = uuid.uuid4().hex
                relative_path = (
                    f"loan_requests/"
                    f"{request_loan.id}/"
                    f"{required_document.id}/"
                    f"{internal_name}{extension}"
                )

                saved_path = default_storage.save(
                    relative_path,
                    uploaded_file,
                )
                saved_paths.append(saved_path)

                document = Document(
                    user=request.user,
                    type_document=requirement.document_type,
                    ip=_get_client_ip(request),
                    size=uploaded_file.size,
                    document_name=uploaded_file.name,
                    internal_name=internal_name,
                    file_type=uploaded_file.content_type or "application/pdf",
                    route=saved_path,
                )
                _save_with_user(document, request.user)

                request_document = RequestLoanDocument(
                    required_document=required_document,
                    document=document,
                    status=RequestLoanDocument.Status.PENDING,
                )
                _save_with_user(request_document, request.user)

                _create_observation(
                    request,
                    request_loan,
                    RequestLoanObservation.Action.DOCUMENT_UPLOADED,
                    (
                        f"Documento adjuntado: "
                        f"{requirement.document_type.name} - "
                        f"{uploaded_file.name}."
                    ),
                )

            _create_observation(
                request,
                request_loan,
                RequestLoanObservation.Action.CREATED,
                (
                    f"Solicitud de préstamo creada para "
                    f"{_person_full_name(employee.person)}. "
                    f"Tipo: {loan_type.name}. "
                    f"Concepto: {type_concept.concept.name}. "
                    f"Monto: ${loan_amount:,.0f}. "
                    f"Plazo: {term} meses."
                ),
            )

        redirect_url = reverse(
            "loan_requests:detail",
            args=[request_loan.pk],
        )

        if is_app_request:
            return JsonResponse({
                "status": "ok",
                "message": "La solicitud de préstamo fue creada correctamente.",
                "redirect_url": redirect_url,
            })

        messages.success(
            request,
            "La solicitud de préstamo fue creada correctamente.",
        )
        return redirect(redirect_url)

    except Exception as error:
        for path in saved_paths:
            try:
                if default_storage.exists(path):
                    default_storage.delete(path)
            except Exception:
                pass

        return fail(
            f"No fue posible crear la solicitud: {error}",
            status=500,
        )

# ============================================================
# DETALLE
# ============================================================
@login_required
def request_loan_detail(request, pk):
    _ensure_request_loan_states(request.user)

    request_loan = get_object_or_404(
        RequestLoan.objects.select_related(
            "request",
            "request__status",
            "state",
            "employee",
            "employee__person",
            "employee__grade",
            "loan_type",
            "type_concept",
            "type_concept__concept",
        ),
        pk=pk,
        is_active=True,
    )

    _assign_default_request_loan_state(request_loan, request.user)

    existing_loan = Loan.objects.filter(
        request=request_loan.request
    ).order_by("id").first()

    action = request.POST.get("action") if request.method == "POST" else None

    # ========================================================
    # EDITAR DATOS GENERALES
    # ========================================================
    if action == "update_request":
        if not _request_data_can_be_edited(request_loan):
            messages.error(
                request,
                "Los datos de la solicitud solo pueden editarse en estado Ingresado o Aprobado Consejo con Modificaciones.",
            )
            return redirect("loan_requests:detail", pk=pk)

        try:
            employee_id = int(request.POST.get("employee_id", 0) or 0)
            loan_type_id = int(request.POST.get("loan_type", 0) or 0)
            type_concept_id = int(request.POST.get("type_concept", 0) or 0)
            term = int(request.POST.get("term", 0) or 0)
            amount_raw = str(request.POST.get("loan_amount", "") or "").strip()
            request_date_raw = str(request.POST.get("request_date", "") or "").strip()

            if employee_id <= 0:
                raise ValueError("Debe seleccionar un funcionario.")
            if loan_type_id <= 0:
                raise ValueError("Debe seleccionar un tipo de préstamo.")
            if type_concept_id <= 0:
                raise ValueError("Debe seleccionar un concepto.")
            if term <= 0:
                raise ValueError("El plazo debe ser mayor a 0.")

            try:
                loan_amount = Decimal(amount_raw)
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError("El monto solicitado no es válido.")

            if loan_amount <= 0:
                raise ValueError("El monto solicitado debe ser mayor a 0.")

            request_date_value = parse_date(request_date_raw)

            if not request_date_value:
                raise ValueError("La fecha de solicitud no es válida.")

            employee = (
                Employee.objects
                .select_related("person", "grade")
                .filter(pk=employee_id, is_active=True)
                .first()
            )
            if not employee:
                raise ValueError("El funcionario seleccionado no existe o está inactivo.")

            loan_type = LoanType.objects.filter(
                pk=loan_type_id,
                is_active=True,
            ).first()
            if not loan_type:
                raise ValueError("El tipo de préstamo seleccionado no es válido.")

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
                raise ValueError(
                    "El concepto seleccionado no corresponde al tipo de préstamo."
                )

            old_employee = _person_full_name(request_loan.employee.person)
            old_type = request_loan.loan_type.name
            old_concept = request_loan.type_concept.concept.name
            old_amount = request_loan.loan_amount
            old_term = request_loan.term
            old_date = request_loan.request_date

            with transaction.atomic():
                request_loan.employee = employee
                request_loan.loan_type = loan_type
                request_loan.type_concept = type_concept
                request_loan.loan_amount = loan_amount
                request_loan.term = term
                request_loan.request_date = request_date_value

                _save_with_user(
                    request_loan,
                    request.user,
                    [
                        "employee",
                        "loan_type",
                        "type_concept",
                        "loan_amount",
                        "term",
                        "request_date",
                    ],
                )

                if existing_loan:
                    _sync_existing_loan_from_request(
                        request,
                        request_loan,
                        existing_loan,
                    )

                _create_observation(
                    request,
                    request_loan,
                    RequestLoanObservation.Action.COMMENT,
                    (
                        "Datos de solicitud actualizados. "
                        f"Funcionario: {old_employee} → {_person_full_name(employee.person)}. "
                        f"Tipo: {old_type} → {loan_type.name}. "
                        f"Concepto: {old_concept} → {type_concept.concept.name}. "
                        f"Monto: ${old_amount:,.0f} → ${loan_amount:,.0f}. "
                        f"Plazo: {old_term} → {term} meses. "
                        f"Fecha: {old_date:%d-%m-%Y} → {request_date_value:%d-%m-%Y}."
                        + (
                            " El préstamo y sus dividendos fueron recalculados."
                            if existing_loan
                            else ""
                        )
                    ),
                )

            messages.success(request, "Los datos de la solicitud fueron actualizados correctamente.")

        except ValueError as error:
            messages.error(request, str(error))
        except Exception as error:
            messages.error(request, f"No fue posible actualizar la solicitud: {error}")

        return redirect("loan_requests:detail", pk=pk)

    # ========================================================
    # CAMBIAR ESTADO
    # ========================================================
    if action == "change_state":
        if _request_is_final(request_loan):
            messages.error(
                request,
                "La solicitud está finalizada y no permite nuevos cambios de estado.",
            )
            return redirect("loan_requests:detail", pk=pk)

        try:
            state_id = int(request.POST.get("request_state", 0) or 0)

            new_state = RequestLoanState.objects.filter(
                pk=state_id,
                is_active=True,
            ).first()

            if not new_state:
                raise ValueError("El estado seleccionado no es válido.")

            old_state = request_loan.state

            if not old_state:
                raise ValueError(
                    "La solicitud no tiene un estado actual válido."
                )

            allowed_state_ids = set(
                _next_request_loan_states(
                    request_loan
                ).values_list(
                    "id",
                    flat=True,
                )
            )

            if new_state.id not in allowed_state_ids:
                raise ValueError(
                    f"No es posible pasar de {old_state.name} a {new_state.name}."
                )

            if new_state.is_paid_state and not existing_loan:
                raise ValueError(
                    "La solicitud no puede pasar a Pagado antes de haber generado el préstamo."
                )

            created_loan = None
            loan_created = False

            with transaction.atomic():
                request_loan.state = new_state
                _save_with_user(request_loan, request.user, ["state"])

                core_request = request_loan.request

                if new_state.is_approval_state:
                    approved_status = _get_or_create_request_status(
                        REQUEST_STATUS_APPROVED,
                        request.user,
                    )
                    core_request.status = approved_status
                    _save_with_user(core_request, request.user, ["status"])

                    created_loan, loan_created = _create_loan_from_request(
                        request,
                        request_loan,
                    )

                elif new_state.is_paid_state:
                    paid_status = _get_or_create_request_status(
                        REQUEST_STATUS_PAID,
                        request.user,
                    )
                    core_request.status = paid_status
                    _save_with_user(core_request, request.user, ["status"])

                else:
                    entered_status = _get_or_create_request_status(
                        REQUEST_STATUS_ENTERED,
                        request.user,
                    )
                    core_request.status = entered_status
                    _save_with_user(core_request, request.user, ["status"])

                _create_observation(
                    request,
                    request_loan,
                    RequestLoanObservation.Action.STATE_CHANGED,
                    (
                        f"Estado modificado. "
                        f"Estado anterior: {old_state.name if old_state else 'Sin estado'}. "
                        f"Nuevo estado: {new_state.name}."
                    ),
                )

                if loan_created and created_loan:
                    _create_observation(
                        request,
                        request_loan,
                        RequestLoanObservation.Action.REQUEST_APPROVED,
                        (
                            f"Solicitud aprobada por consejo. "
                            f"Se creó el préstamo #{created_loan.id} "
                            f"con {request_loan.term} dividendos."
                        ),
                    )

            success_message = f"Estado actualizado a {new_state.name}."

            if loan_created and created_loan:
                success_message += f" Se creó el préstamo #{created_loan.id}."

            messages.success(request, success_message)

        except ValueError as error:
            messages.error(request, str(error))
        except Exception as error:
            messages.error(request, f"No fue posible cambiar el estado: {error}")

        return redirect("loan_requests:detail", pk=pk)

    # Indicamos cuales son los ID que pueden asignar o deribar responsabilidades a personas
    # En este caso, las jefaturas deriban a sus áreas.
    can_assign = request.user.groups.filter(name__in=["Jefe Prestamos", "Jefe Contabilidad"]).exists()

    if action == "assign_group":
        if not can_assign:
            message.error(request,  "No tiene permisos para asignar solicitudes.")
            return redirect("loan_request:detail", pk=pk)

        employee_id = request.POST.get("assigment_employee")
        area_name = _normalize_spaces(request.POST.get("assigment_area"))

        if employee_id and area_name:
            assigned_emp = Employee.objects.filter(pk=employee_id, is_active=True).select_related("person").first()
            if assigned_emp:
                emp_name = _person_full_name(assigned_emp.person)
                _create_observation(
                    request,
                    request_loan,
                    RequestLoanObservation.Action.COMMENT,
                    f"Solicitud asignada a: {emp_name} ({area_name}).",
                )
                message.success(request, f"Solicitud asignada correctamente a {emp_name} ({area_name}).")
            else:
                message.error(request, "El trabajador seleccionado no es válido.")
        else:
            message.error(request, "Debe seleccionar un área y un responsable.")
        
        return redirect("loan_request:detail", pk=pk)

    required_documents = (
        request_loan.required_documents
        .filter(is_active=True)
        .select_related("document_type")
        .order_by("id")
    )

    document_rows = []

    for required in required_documents:
        documents = list(
            required.documents
            .filter(is_active=True)
            .select_related(
                "document",
                "document__type_document",
                "validated_by",
            )
            .order_by("-id")
        )

        approved_count = sum(
            1
            for item in documents
            if item.status == RequestLoanDocument.Status.APPROVED
        )

        pending_count = sum(
            1
            for item in documents
            if item.status == RequestLoanDocument.Status.PENDING
        )

        rejected_count = sum(
            1
            for item in documents
            if item.status == RequestLoanDocument.Status.REJECTED
        )

        document_rows.append({
            "required": required,
            "documents": documents,
            "documents_count": len(documents),
            "approved_count": approved_count,
            "pending_count": pending_count,
            "rejected_count": rejected_count,
            "can_upload": not _request_is_final(request_loan),
        })

    observations = (
        request_loan.observations
        .filter(is_active=True)
        .select_related("observation", "observation__user")
        .order_by("-id")
    )

    loan_types = LoanType.objects.filter(
        is_active=True
    ).order_by("name", "id")

    request_states = _next_request_loan_states(
        request_loan
    )

    # Se lee asignación de persona y área
    assigment_obs = (
        request_loan.observations
        .filter(
            is_active = True,
            observation__comment__startswith = "Solicitud asignada a: "
            )
            .select_related("observation")
            .order_by("-id")
            .first()
    )

    current_assigment = "Sin asignar"
    if assigment_obs and assigment_obs.comment:
        current_assigment = (
            assigment_obs.observation.comment
            .replace("icitud asignada a: ", "")
            .strip()
            .rstrip(".")
        )

    active_employees = (
        Employee.objects
        .filter(is_active = True)
        .select_related("person")
        .order_by("person__first_name", "person__last_name_1")
    )

    person = request_loan.employee.person
    is_final = _request_is_final(request_loan)
    has_loan = bool(existing_loan)

    context = {
        "request_loan": request_loan,
        "person": person,
        "person_name": _person_full_name(person),
        "person_rut": _format_rut(person),
        "employee_grade": str(request_loan.employee.grade) if request_loan.employee.grade else "",
        "loan_types": loan_types,
        "request_states": request_states,
        "has_next_state": request_states.exists(),
        "timeline": _request_timeline(request_loan),
        "document_rows": document_rows,
        "observations": observations,
        "can_edit": _request_data_can_be_edited(request_loan),
        "can_change_state": not is_final,
        "has_loan": has_loan,
        "is_final": is_final,
        "is_rejected": _request_is_rejected(request_loan),
        "can_assign": can_assign,
        "current_assigment": current_assigment,
        "active_employees": active_employees,
    }

    return render(
        request,
        "prestamos/loan_requests/request_loan_detail.html",
        context,
    )


# ============================================================
# DETALLE MODAL
# ============================================================
@login_required
@require_GET
def request_loan_detail_modal(request, pk):
    _ensure_request_loan_states(request.user)
    request_loan = get_object_or_404(
        RequestLoan.objects.select_related(
            "request",
            "request__status",
            "state",
            "employee",
            "employee__person",
            "employee__grade",
            "loan_type",
            "type_concept",
            "type_concept__concept",
        ),
        pk=pk,
        is_active=True,
    )

    _assign_default_request_loan_state(
        request_loan,
        request.user,
    )

    required_documents = (
        request_loan.required_documents
        .filter(is_active=True)
        .select_related("document_type")
        .order_by("id")
    )

    document_rows = []
    total_documents = 0
    approved_documents = 0
    pending_documents = 0
    rejected_documents = 0

    for required in required_documents:
        documents = list(
            required.documents
            .filter(is_active=True)
            .select_related(
                "document",
                "document__type_document",
                "validated_by",
            )
            .order_by("-id")
        )

        approved_count = sum(
            1
            for item in documents
            if item.status == RequestLoanDocument.Status.APPROVED
        )

        pending_count = sum(
            1
            for item in documents
            if item.status == RequestLoanDocument.Status.PENDING
        )

        rejected_count = sum(
            1
            for item in documents
            if item.status == RequestLoanDocument.Status.REJECTED
        )

        total_documents += len(documents)
        approved_documents += approved_count
        pending_documents += pending_count
        rejected_documents += rejected_count

        document_rows.append({
            "required": required,
            "documents": documents,
            "documents_count": len(documents),
            "approved_count": approved_count,
            "pending_count": pending_count,
            "rejected_count": rejected_count,
            "can_upload": not _request_is_final(request_loan),
        })

    observations = (
        request_loan.observations
        .filter(is_active=True)
        .select_related("observation", "observation__user")
        .order_by("-id")
    )

    person = request_loan.employee.person

    return render(
        request,
        "prestamos/loan_requests/request_loan_detail_modal.html",
        {
            "request_loan": request_loan,
            "person": person,
            "person_name": _person_full_name(person),
            "person_rut": _format_rut(person),
            "employee_grade": (
                str(request_loan.employee.grade)
                if request_loan.employee.grade
                else ""
            ),
            "document_rows": document_rows,
            "observations": observations,
            "total_documents_count": total_documents,
            "approved_documents_count": approved_documents,
            "pending_documents_count": pending_documents,
            "rejected_documents_count": rejected_documents,
            "timeline": _request_timeline(request_loan),
            "is_rejected": _request_is_rejected(request_loan),
            "is_final": _request_is_final(request_loan),
        },
    )

# ============================================================
# ADJUNTAR DOCUMENTO
# ============================================================
@login_required
@require_POST
def request_loan_document_upload(request, pk, required_id):
    request_loan = get_object_or_404(
        RequestLoan.objects.select_related("request", "request__status"),
        pk=pk,
        is_active=True,
    )

    if _request_is_final(request_loan):
        messages.error(request, "La solicitud está finalizada y no permite nuevos documentos.")
        return redirect("loan_requests:detail", pk=pk)

    required = get_object_or_404(
        RequestLoanRequiredDocument.objects.select_related("document_type"),
        pk=required_id,
        request_loan=request_loan,
        is_active=True,
    )

    uploaded_file = request.FILES.get("document")

    try:
        _validate_pdf(uploaded_file)

        with transaction.atomic():
            internal_name = uuid.uuid4().hex
            extension = Path(uploaded_file.name).suffix.lower()
            relative_path = f"loan_requests/{request_loan.id}/{required.id}/{internal_name}{extension}"
            saved_path = default_storage.save(relative_path, uploaded_file)

            document = Document(
                user=request.user,
                type_document=required.document_type,
                ip=_get_client_ip(request),
                size=uploaded_file.size,
                document_name=uploaded_file.name,
                internal_name=internal_name,
                file_type=uploaded_file.content_type or "application/pdf",
                route=saved_path,
            )
            _save_with_user(document, request.user)

            relation = RequestLoanDocument(
                required_document=required,
                document=document,
                status=RequestLoanDocument.Status.PENDING,
            )
            _save_with_user(relation, request.user)

            _create_observation(
                request,
                request_loan,
                RequestLoanObservation.Action.DOCUMENT_UPLOADED,
                f"Documento adjuntado: {required.document_type.name} - {uploaded_file.name}.",
            )

        messages.success(request, "Documento adjuntado correctamente.")

    except Exception as exc:
        messages.error(request, str(exc))

    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# VER DOCUMENTO
# ============================================================
@login_required
@require_GET
def request_loan_document_view(request, pk, document_id):
    relation = get_object_or_404(
        RequestLoanDocument.objects.select_related(
            "document",
            "required_document",
            "required_document__request_loan",
        ),
        pk=document_id,
        required_document__request_loan_id=pk,
        is_active=True,
    )

    if not relation.document.route:
        raise Http404("El documento no tiene una ruta asociada.")

    try:
        file_handle = default_storage.open(relation.document.route, "rb")
    except FileNotFoundError:
        raise Http404("El archivo no existe.")

    return FileResponse(
        file_handle,
        content_type=relation.document.file_type or "application/pdf",
        filename=relation.document.document_name,
    )


# ============================================================
# APROBAR DOCUMENTO
# ============================================================
@login_required
@require_POST
def request_loan_document_approve(request, pk, document_id):
    with transaction.atomic():
        relation = get_object_or_404(
            RequestLoanDocument.objects.select_for_update().select_related(
                "required_document",
                "required_document__request_loan",
                "required_document__request_loan__request",
                "required_document__request_loan__request__status",
                "required_document__document_type",
            ),
            pk=document_id,
            required_document__request_loan_id=pk,
            is_active=True,
        )

        request_loan = relation.required_document.request_loan

        if _request_is_final(request_loan):
            messages.error(request, "La solicitud está finalizada.")
            return redirect("loan_requests:detail", pk=pk)

        if relation.status != RequestLoanDocument.Status.PENDING:
            messages.error(request, "El documento ya fue procesado.")
            return redirect("loan_requests:detail", pk=pk)

        relation.status = RequestLoanDocument.Status.APPROVED
        relation.rejection_comment = None
        relation.validated_by = request.user
        relation.validated_at = timezone.now()
        _save_with_user(
            relation,
            request.user,
            ["status", "rejection_comment", "validated_by", "validated_at"],
        )

        _create_observation(
            request,
            request_loan,
            RequestLoanObservation.Action.DOCUMENT_APPROVED,
            f"Documento aprobado: {relation.required_document.document_type.name}.",
        )

    messages.success(request, "Documento aprobado correctamente.")
    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# RECHAZAR DOCUMENTO
# ============================================================
@login_required
@require_POST
def request_loan_document_reject(request, pk, document_id):
    comment = _normalize_spaces(request.POST.get("comment"))

    if not comment:
        messages.error(request, "Debe indicar el motivo del rechazo.")
        return redirect("loan_requests:detail", pk=pk)

    with transaction.atomic():
        relation = get_object_or_404(
            RequestLoanDocument.objects.select_for_update().select_related(
                "required_document",
                "required_document__request_loan",
                "required_document__request_loan__request",
                "required_document__request_loan__request__status",
                "required_document__document_type",
            ),
            pk=document_id,
            required_document__request_loan_id=pk,
            is_active=True,
        )

        request_loan = relation.required_document.request_loan

        if _request_is_final(request_loan):
            messages.error(request, "La solicitud está finalizada.")
            return redirect("loan_requests:detail", pk=pk)

        if relation.status != RequestLoanDocument.Status.PENDING:
            messages.error(request, "El documento ya fue procesado.")
            return redirect("loan_requests:detail", pk=pk)

        relation.status = RequestLoanDocument.Status.REJECTED
        relation.rejection_comment = comment
        relation.validated_by = request.user
        relation.validated_at = timezone.now()
        _save_with_user(
            relation,
            request.user,
            ["status", "rejection_comment", "validated_by", "validated_at"],
        )

        _create_observation(
            request,
            request_loan,
            RequestLoanObservation.Action.DOCUMENT_REJECTED,
            f"Documento rechazado: {relation.required_document.document_type.name}. Motivo: {comment}",
        )

    messages.success(request, "Documento rechazado correctamente.")
    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# APROBAR SOLICITUD
# ============================================================
@login_required
@require_POST
def request_loan_approve(request, pk):
    try:
        with transaction.atomic():
            _ensure_request_loan_states(request.user)

            request_loan = get_object_or_404(
                RequestLoan.objects.select_for_update().select_related(
                    "request",
                    "request__status",
                    "state",
                    "employee",
                    "employee__person",
                    "loan_type",
                    "type_concept",
                    "type_concept__concept",
                ),
                pk=pk,
                is_active=True,
            )

            _assign_default_request_loan_state(request_loan, request.user)

            if _request_is_final(request_loan):
                raise ValueError("La solicitud ya se encuentra finalizada.")

            approval_state = (
                RequestLoanState.objects
                .filter(is_active=True, is_approval_state=True)
                .order_by("sequence", "id")
                .first()
            )

            if not approval_state:
                raise ValueError("No existe un estado de aprobación configurado.")

            old_state = request_loan.state
            request_loan.state = approval_state
            _save_with_user(request_loan, request.user, ["state"])

            approved_status = _get_or_create_request_status(
                REQUEST_STATUS_APPROVED,
                request.user,
            )

            core_request = request_loan.request
            core_request.status = approved_status
            _save_with_user(core_request, request.user, ["status"])

            loan, created = _create_loan_from_request(request, request_loan)

            _create_observation(
                request,
                request_loan,
                RequestLoanObservation.Action.STATE_CHANGED,
                (
                    f"Estado modificado. "
                    f"Estado anterior: {old_state.name if old_state else 'Sin estado'}. "
                    f"Nuevo estado: {approval_state.name}."
                ),
            )

            if created:
                _create_observation(
                    request,
                    request_loan,
                    RequestLoanObservation.Action.REQUEST_APPROVED,
                    (
                        f"Solicitud aprobada por consejo. "
                        f"Se creó el préstamo #{loan.id} "
                        f"con {request_loan.term} dividendos."
                    ),
                )

        messages.success(
            request,
            f"Solicitud aprobada correctamente. Préstamo #{loan.id}.",
        )

    except ValueError as error:
        messages.error(request, str(error))
    except Exception as error:
        messages.error(request, f"No fue posible aprobar la solicitud: {error}")

    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# RECHAZAR SOLICITUD
# ============================================================
@login_required
@require_POST
def request_loan_reject(request, pk):
    comment = _normalize_spaces(request.POST.get("comment"))

    if not comment:
        messages.error(request, "Debe indicar el motivo del rechazo de la solicitud.")
        return redirect("loan_requests:detail", pk=pk)

    with transaction.atomic():
        request_loan = get_object_or_404(
            RequestLoan.objects.select_for_update().select_related(
                "request",
                "request__status",
            ),
            pk=pk,
            is_active=True,
        )

        if _request_is_final(request_loan):
            messages.error(request, "La solicitud ya se encuentra finalizada.")
            return redirect("loan_requests:detail", pk=pk)

        if Loan.objects.filter(request=request_loan.request).exists():
            messages.error(
                request,
                "La solicitud ya generó un préstamo y no puede rechazarse.",
            )
            return redirect("loan_requests:detail", pk=pk)

        previous_status = request_loan.request.status.status_type

        rejected_status = _get_or_create_request_status(REQUEST_STATUS_REJECTED, request.user)
        core_request = request_loan.request
        core_request.status = rejected_status
        _save_with_user(core_request, request.user, ["status"])

        _create_observation(
            request,
            request_loan,
            RequestLoanObservation.Action.REQUEST_REJECTED,
            (
                f"Solicitud de préstamo rechazada. "
                f"Estado anterior: {previous_status}. "
                f"Motivo: {comment}"
            ),
        )

    messages.success(request, "Solicitud rechazada correctamente.")
    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# AGREGAR OBSERVACIÓN MANUAL
# ============================================================
@login_required
@require_POST
def request_loan_add_observation(request, pk):
    request_loan = get_object_or_404(RequestLoan, pk=pk, is_active=True)
    comment = _normalize_spaces(request.POST.get("comment"))

    if not comment:
        messages.error(request, "Debe ingresar una observación.")
        return redirect("loan_requests:detail", pk=pk)

    _create_observation(
        request,
        request_loan,
        RequestLoanObservation.Action.COMMENT,
        comment,
    )

    messages.success(request, "Observación agregada correctamente.")
    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# CONCEPTOS POR TIPO DE PRESTAMO
# ============================================================
@login_required
@require_GET
def request_loan_concepts(request):
    try:
        loan_type_id = int(
            request.GET.get("loan_type_id", 0) or 0
        )

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
