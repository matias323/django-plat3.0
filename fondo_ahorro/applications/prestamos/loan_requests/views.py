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
)


REQUEST_TYPE_LOAN = "Loan"
REQUEST_STATUS_ENTERED = "INGRESADO"
REQUEST_STATUS_APPROVED = "APROBADO"
REQUEST_STATUS_REJECTED = "RECHAZADO"

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


def _request_is_final(request_loan):
    status = _normalize_spaces(request_loan.request.status.status_type).upper()
    return status in {REQUEST_STATUS_APPROVED, REQUEST_STATUS_REJECTED}


def _latest_document(required_document):
    return required_document.documents.select_related(
        "document",
        "document__type_document",
        "validated_by",
    ).order_by("-id").first()


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

    search = _normalize_spaces(request.GET.get("search[value]", ""))

    queryset = (
        RequestLoan.objects
        .select_related(
            "request",
            "request__status",
            "request__request_type",
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
            "status": item.request.status.status_type,
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
    request_loan = get_object_or_404(
        RequestLoan.objects.select_related(
            "request",
            "request__status",
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

    required_documents = (
        request_loan.required_documents
        .filter(is_active=True)
        .select_related("document_type")
        .order_by("id")
    )

    document_rows = []

    for required in required_documents:
        latest = _latest_document(required)

        document_rows.append({
            "required": required,
            "latest": latest,
            "has_document": latest is not None,
            "can_upload": (
                not _request_is_final(request_loan)
                and (latest is None or latest.status == RequestLoanDocument.Status.REJECTED)
            ),
            "can_validate": (
                not _request_is_final(request_loan)
                and latest is not None
                and latest.status == RequestLoanDocument.Status.PENDING
            ),
        })

    observations = (
        request_loan.observations
        .filter(is_active=True)
        .select_related("observation", "observation__user")
        .order_by("-id")
    )

    person = request_loan.employee.person

    context = {
        "request_loan": request_loan,
        "person": person,
        "person_name": _person_full_name(person),
        "person_rut": _format_rut(person),
        "employee_grade": str(request_loan.employee.grade) if request_loan.employee.grade else "",
        "document_rows": document_rows,
        "observations": observations,
        "can_approve": request_loan.can_be_approved() and not _request_is_final(request_loan),
        "is_final": _request_is_final(request_loan),
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
    request_loan = get_object_or_404(
        RequestLoan.objects.select_related(
            "request",
            "request__status",
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

    required_documents = (
        request_loan.required_documents
        .filter(is_active=True)
        .select_related("document_type")
        .order_by("id")
    )

    document_rows = []
    approved_documents = 0

    for required in required_documents:
        latest = _latest_document(required)

        if latest and latest.status == RequestLoanDocument.Status.APPROVED:
            approved_documents += 1

        document_rows.append({
            "required": required,
            "latest": latest,
            "has_document": latest is not None,
            "can_upload": (
                not _request_is_final(request_loan)
                and (
                    latest is None
                    or latest.status == RequestLoanDocument.Status.REJECTED
                )
            ),
            "can_validate": (
                not _request_is_final(request_loan)
                and latest is not None
                and latest.status == RequestLoanDocument.Status.PENDING
            ),
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
            "required_documents_count": len(document_rows),
            "approved_documents_count": approved_documents,
            "can_approve": (
                request_loan.can_be_approved()
                and not _request_is_final(request_loan)
            ),
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

    latest = _latest_document(required)

    if latest and latest.status != RequestLoanDocument.Status.REJECTED:
        messages.error(
            request,
            "Solo puede adjuntar un nuevo archivo si no existe uno o si el último fue rechazado.",
        )
        return redirect("loan_requests:detail", pk=pk)

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

        latest = _latest_document(relation.required_document)

        if not latest or latest.id != relation.id:
            messages.error(request, "Solo puede validarse la última versión del documento.")
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

        latest = _latest_document(relation.required_document)

        if not latest or latest.id != relation.id:
            messages.error(request, "Solo puede rechazarse la última versión del documento.")
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

    messages.success(request, "Documento rechazado. Ahora puede adjuntarse una nueva versión.")
    return redirect("loan_requests:detail", pk=pk)


# ============================================================
# APROBAR SOLICITUD
# ============================================================
@login_required
@require_POST
def request_loan_approve(request, pk):
    try:
        with transaction.atomic():
            request_loan = get_object_or_404(
                RequestLoan.objects.select_for_update().select_related(
                    "request",
                    "request__status",
                    "employee",
                    "employee__person",
                    "loan_type",
                    "type_concept",
                    "type_concept__concept",
                ),
                pk=pk,
                is_active=True,
            )

            if _request_is_final(request_loan):
                raise ValueError("La solicitud ya se encuentra finalizada.")

            if not request_loan.can_be_approved():
                raise ValueError(
                    "La solicitud no puede aprobarse hasta que todos los documentos requeridos estén adjuntos y aprobados."
                )

            existing_loan = Loan.objects.filter(request=request_loan.request).order_by("id").first()
            if existing_loan:
                raise ValueError(f"La solicitud ya generó el préstamo #{existing_loan.id}.")

            # Valores fijos definidos por ID para este flujo.
            # Tasa 1 = 4%, método 1 = Remuneración,
            # estado préstamo 1 = Vigente, estado dividendo 1 = Pendiente.
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

            approved_status = _get_or_create_request_status(REQUEST_STATUS_APPROVED, request.user)
            core_request = request_loan.request
            core_request.status = approved_status
            _save_with_user(core_request, request.user, ["status"])

            _create_observation(
                request,
                request_loan,
                RequestLoanObservation.Action.REQUEST_APPROVED,
                f"Solicitud de préstamo aprobada. Se creó el préstamo #{loan.id} con {term} dividendos.",
            )

        messages.success(
            request,
            f"Solicitud aprobada correctamente. Se creó el préstamo #{loan.id}.",
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

        rejected_status = _get_or_create_request_status(REQUEST_STATUS_REJECTED, request.user)
        core_request = request_loan.request
        core_request.status = rejected_status
        _save_with_user(core_request, request.user, ["status"])

        _create_observation(
            request,
            request_loan,
            RequestLoanObservation.Action.REQUEST_REJECTED,
            f"Solicitud de préstamo rechazada. Motivo: {comment}",
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
