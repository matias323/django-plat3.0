import unicodedata
import uuid
from calendar import monthrange
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models.document import Document, DocumentType
from core.models.employee import Employee
from core.models.observation import Observation
from core.models.partner import Partner, PartnerContribution, PartnerContributionType
from core.models.person import Person, PersonDiprecaCode

from ..models.loan import (
    Loan, LoanCollectionMethod, LoanCollectionMethodRecord, LoanDocument,
    LoanGuarantor, LoanGuarantorMovement, LoanInstallment, LoanInstallmentStatus,
    LoanRate, LoanRateRecord, LoanStatus,
)
from ..models.payment import (
    LoanDocumentNumber, LoanDocumentNumberType, LoanPayment,
    LoanPaymentContribution, LoanPaymentDeposit, LoanPaymentDocument,
    LoanPaymentExternal, LoanPaymentExternalDocument, LoanPaymentExternalMethod,
    LoanPaymentStatus, LoanPaymentType,
)


MAX_FILE_SIZE = 10 * 1024 * 1024
MONEY = Decimal("0.01")

FINANCIAL_ACTIONS = {
    "pay-installment",
    "no-collection",
    "prepayment",
    "amortization",
    "overdue",
    "insurance",
    "collection-method",
    "rate",
}


# ============================================================
# FUNCIONES GENERALES
def _normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


# ============================================================
# ESTADO FINANCIERO DEL PRESTAMO
def _financial_operations_locked(loan):
    return int(loan.status_id or 0) in {4, 5}


def _has_field(model, field_name):
    return any(field.name == field_name for field in model._meta.get_fields())


def _save_with_user(instance, user):
    if _has_field(instance.__class__, "user_create") and _has_field(instance.__class__, "user_update"):
        instance.save(user=user)
    else:
        instance.save()
    return instance


def _create_with_user(model, audit_user=None, **values):
    return _save_with_user(model(**values), audit_user)


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def _decimal(value, label="Monto"):
    try:
        raw = str(value or "0").strip()
        raw = raw.replace("$", "").replace("CLP", "").replace("clp", "").replace(" ", "")

        if not raw:
            raw = "0"

        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")

        elif "," in raw:
            parts = raw.split(",")

            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                raw = raw.replace(",", ".")
            else:
                raw = raw.replace(",", "")

        elif "." in raw:
            parts = raw.split(".")

            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
                raw = raw.replace(".", "")

        result = Decimal(raw)

    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} inválido.")

    if result < 0:
        raise ValueError(f"{label} no puede ser negativo.")

    return result.quantize(MONEY, rounding=ROUND_HALF_UP)


def _document_url(document):
    if not document or not document.route:
        return ""

    try:
        return default_storage.url(document.route)
    except Exception:
        return document.route


def _validate_pdf(uploaded_file, required=True):
    if not uploaded_file:
        if required:
            raise ValueError("Debe adjuntar un documento PDF.")
        return

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError("El documento no puede superar los 10 MB.")

    suffix = Path(uploaded_file.name).suffix.lower()
    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()

    if suffix != ".pdf" and content_type != "application/pdf":
        raise ValueError("El documento debe estar en formato PDF.")

    header = uploaded_file.read(5)
    uploaded_file.seek(0)

    if header != b"%PDF-":
        raise ValueError("El archivo seleccionado no corresponde a un PDF válido.")


def _reference(model, aliases, fallback_id=None):
    aliases = {_normalize(value) for value in aliases}
    queryset = model.objects.all()

    if _has_field(model, "is_active"):
        queryset = queryset.filter(is_active=True)

    for instance in queryset:
        if _normalize(getattr(instance, "name", "")) in aliases:
            return instance

    if fallback_id:
        instance = queryset.filter(pk=fallback_id).first()
        if instance:
            return instance

    raise ValueError(f"No se encontró la configuración requerida en {model._meta.verbose_name_plural}.")


def _document_type(name, user):
    document_type = DocumentType.objects.filter(name__iexact=name).first()

    if document_type:
        if hasattr(document_type, "is_active") and not document_type.is_active:
            document_type.is_active = True
            _save_with_user(document_type, user)
        return document_type

    return _create_with_user(DocumentType, user, name=name)


def _save_document(request, uploaded_file, loan, category, document_type=None, document_type_name=None):
    _validate_pdf(uploaded_file)

    if not document_type:
        document_type = _document_type(document_type_name or "Documento Préstamo", request.user)

    internal_name = f"{uuid.uuid4().hex}.pdf"
    route = default_storage.save(f"loans/{loan.id}/{category}/{internal_name}", uploaded_file)

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

    return document, route


def _create_observation(request, comment):
    values = {"comment": comment}

    if _has_field(Observation, "user"):
        values["user"] = request.user

    if _has_field(Observation, "ip"):
        values["ip"] = _get_client_ip(request)

    if _has_field(Observation, "time"):
        values["time"] = timezone.localtime().time()

    if _has_field(Observation, "date"):
        values["date"] = timezone.localdate()

    return _create_with_user(Observation, request.user, **values)


def _person_full_name(person):
    if not person:
        return ""

    return " ".join(
        str(value).strip()
        for value in [
            getattr(person, "first_name", ""),
            getattr(person, "second_name", ""),
            getattr(person, "last_name_1", ""),
            getattr(person, "last_name_2", ""),
        ]
        if value
    )


def _person_rut(person):
    return f"{person.rut}-{person.dv}" if person else ""


def _user_name(user):
    if not user:
        return "-"

    if hasattr(user, "get_full_name"):
        value = str(user.get_full_name() or "").strip()
        if value:
            return value

    return str(user)


def _partner_for_loan(loan):
    return Partner.objects.filter(person_id=loan.person_id, is_active=True).first()


def _contributions_for_loan(loan):
    partner = _partner_for_loan(loan)

    if not partner:
        return PartnerContribution.objects.none()

    return (
        PartnerContribution.objects
        .filter(
            partner=partner,
            is_active=True,
            contribution_type__is_active=True,
            amount__gt=0,
        )
        .select_related("contribution_type")
        .order_by("contribution_type__description")
    )


def _pending_installment_status():
    return _reference(LoanInstallmentStatus, ["Pendiente", "Pending"], 1)


def _no_collection_status():
    return _reference(LoanInstallmentStatus, ["No mandar a cobro", "No Cobro", "No cobrar"], 9)


def _pending_amortization_status():
    return _reference(LoanInstallmentStatus, ["Por amortizar", "Pendiente amortización"], 5)


def _pending_payment_installment_status():
    return _reference(
        LoanInstallmentStatus,
        ["Solicitud de pago", "Pago pendiente", "Pendiente aprobación pago"],
        8,
    )


def _pending_payment_status():
    return _reference(LoanPaymentStatus, ["Pendiente", "Pending"], 1)


def _payment_type(aliases, fallback_id):
    return _reference(LoanPaymentType, aliases, fallback_id)


def _loan_status(aliases, fallback_id):
    return _reference(LoanStatus, aliases, fallback_id)


def _collection_is_external(collection_method):
    value = _normalize(collection_method.name if collection_method else "")
    return "extrasistema" in value or ("extra" in value and "sistema" in value)


def _external_method_kind(method):
    name = _normalize(method.name if method else "")

    if (method and method.pk == 1) or "aporte" in name:
        return "contribution"

    if (method and method.pk == 2) or "deposit" in name:
        return "deposit"

    return "other"


def _available_contribution(contribution_type_id, loan):
    partner = _partner_for_loan(loan)

    if not partner:
        return Decimal("0")

    contribution = (
        PartnerContribution.objects
        .filter(partner=partner, contribution_type_id=contribution_type_id, is_active=True)
        .order_by("-id")
        .first()
    )

    return Decimal(contribution.amount or 0) if contribution else Decimal("0")


def _document_number_type(name, fallback_id, user):
    try:
        return _reference(LoanDocumentNumberType, [name], fallback_id)
    except ValueError:
        return _create_with_user(LoanDocumentNumberType, user, name=name)


def _validate_document_number_unique(number_type, number, annual=False, year=None):
    number = int(number)

    # Bloquea el tipo durante la transacción para evitar que dos solicitudes
    # concurrentes validen el mismo número al mismo tiempo.
    LoanDocumentNumberType.objects.select_for_update().get(pk=number_type.pk)

    queryset = LoanDocumentNumber.objects.filter(
        number_type=number_type,
        number=number,
        is_active=True,
    )

    if annual:
        year = int(year or timezone.localdate().year)
        queryset = queryset.filter(document__created_at__year=year)

    if not queryset.exists():
        return

    normalized_type = _normalize(number_type.name)

    if "deposit" in normalized_type:
        raise ValueError(
            f"El número de depósito {number} ya fue utilizado durante el año {year}."
        )

    if "resolucion" in normalized_type:
        raise ValueError(f"El número de resolución {number} ya fue utilizado.")

    raise ValueError(f"El número {number} ya fue utilizado para {number_type.name}.")


def _create_payment(request, loan, payment_type, amount, installment=None):
    return _create_with_user(
        LoanPayment,
        request.user,
        installment=installment,
        loan=loan,
        payment_type=payment_type,
        amount=amount,
        previous_balance=loan.principal_balance or 0,
        previous_installment=installment.amount if installment else 0,
        status_changed_at=timezone.now(),
        ip=_get_client_ip(request),
        status=_pending_payment_status(),
    )


def _parse_indexed_rows(request, prefix):
    indexes = set()

    for key in list(request.POST.keys()) + list(request.FILES.keys()):
        if not key.startswith(prefix + "["):
            continue

        index = key[len(prefix) + 1:].split("]", 1)[0]

        if index.isdigit():
            indexes.add(int(index))

    rows = []

    for index in sorted(indexes):
        rows.append({
            "method": request.POST.get(f"{prefix}[{index}][method]", ""),
            "amount": request.POST.get(f"{prefix}[{index}][amount]", ""),
            "contribution": request.POST.get(f"{prefix}[{index}][contribution]", ""),
            "detail": request.POST.get(f"{prefix}[{index}][detail]", ""),
            "document": request.FILES.get(f"{prefix}[{index}][document]"),
        })

    return rows


def _parse_contribution_amounts(request):
    rows = []

    for key, raw_value in request.POST.items():
        if not key.startswith("contribution_"):
            continue

        try:
            contribution_type_id = int(key.split("_", 1)[1])
        except (TypeError, ValueError):
            continue

        amount = _decimal(raw_value, "Monto de aporte")

        if amount > 0:
            rows.append((contribution_type_id, amount))

    return rows


def _add_months(value, months):
    month_index = value.month - 1 + int(months or 0)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _first_day_after_months(months):
    return _add_months(timezone.localdate().replace(day=1), months)


def _french_schedule(principal, annual_rate, count):
    principal = Decimal(principal or 0).quantize(MONEY)
    annual = Decimal(annual_rate or 0) / Decimal("100")
    count = int(count or 0)

    if principal <= 0 or count <= 0:
        return []

    monthly_float = (1 + float(annual)) ** (1 / 12) - 1
    monthly = Decimal(str(monthly_float))

    if monthly == 0:
        payment = (principal / Decimal(count)).quantize(MONEY, rounding=ROUND_HALF_UP)
    else:
        factor = (Decimal("1") + monthly) ** count
        payment = (principal * monthly * factor / (factor - Decimal("1"))).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )

    balance = principal
    rows = []

    for index in range(1, count + 1):
        interest = (balance * monthly).quantize(MONEY, rounding=ROUND_HALF_UP)
        capital = (payment - interest).quantize(MONEY, rounding=ROUND_HALF_UP)

        if index == count:
            capital = balance
            payment = (capital + interest).quantize(MONEY, rounding=ROUND_HALF_UP)

        rows.append((payment, capital, interest))
        balance = max(Decimal("0"), balance - capital)

    return rows


def _recalculate_pending_installments(loan, user):
    pending = _pending_installment_status()
    no_collection = _no_collection_status()

    installments = list(
        LoanInstallment.objects
        .filter(
            loan=loan,
            status__in=[pending, no_collection],
            is_active=True,
        )
        .order_by("installment_number")
    )

    schedule = _french_schedule(
        loan.principal_balance,
        loan.rate.rate if loan.rate else 0,
        len(installments),
    )

    for installment, values in zip(installments, schedule):
        installment.amount, installment.principal, installment.interest = values
        _save_with_user(installment, user)

    loan.interest_balance = sum(
        (Decimal(item.interest or 0) for item in installments),
        Decimal("0"),
    )
    loan.interest_amount = (
        Decimal(loan.interest_paid or 0)
        + Decimal(loan.interest_balance or 0)
    )
    _save_with_user(loan, user)


def _create_child_installments(parent, child, user):
    pending = _pending_installment_status()
    schedule = _french_schedule(
        child.principal_balance,
        child.rate.rate if child.rate else 0,
        child.term,
    )

    for index, values in enumerate(schedule, start=1):
        amount, principal, interest = values

        _create_with_user(
            LoanInstallment,
            user,
            loan=child,
            collection_method=child.collection_method,
            status=pending,
            due_date=_add_months(parent.start_date or timezone.localdate(), index - 1),
            amount=amount,
            principal=principal,
            interest=interest,
            installment_number=index,
        )

    child.interest_amount = sum((row[2] for row in schedule), Decimal("0"))
    child.interest_balance = child.interest_amount
    _save_with_user(child, user)


# ============================================================
# TIPOS DE APORTE DISPONIBLES
def _contribution_options_for_loan(loan):
    partner = _partner_for_loan(loan)

    contribution_types = (
        PartnerContributionType.objects
        .filter(is_active=True)
        .order_by("description", "id")
    )

    if not partner:
        return [
            {
                "id": contribution_type.id,
                "description": contribution_type.description,
                "amount": Decimal("0"),
            }
            for contribution_type in contribution_types
        ]

    balances = {
        contribution.contribution_type_id: Decimal(contribution.amount or 0)
        for contribution in (
            PartnerContribution.objects
            .filter(
                partner=partner,
                is_active=True,
            )
            .select_related("contribution_type")
            .order_by("id")
        )
    }

    return [
        {
            "id": contribution_type.id,
            "description": contribution_type.description,
            "amount": balances.get(
                contribution_type.id,
                Decimal("0"),
            ),
        }
        for contribution_type in contribution_types
    ]


# ============================================================
# DIPRECA
def _dipreca_person_field():
    for name in ["person", "persona"]:
        if _has_field(PersonDiprecaCode, name):
            return name
    return None


def _dipreca_code_field():
    for name in ["code", "dipreca_code", "codigo", "codigo_dipreca"]:
        if _has_field(PersonDiprecaCode, name):
            return name
    return None


def _get_person_dipreca(person):
    person_field = _dipreca_person_field()

    if not person_field:
        return None

    filters = {person_field: person}

    if _has_field(PersonDiprecaCode, "is_active"):
        filters["is_active"] = True

    return PersonDiprecaCode.objects.filter(**filters).order_by("-id").first()


def _dipreca_document_field():
    for name in ["document", "documento"]:
        if _has_field(PersonDiprecaCode, name):
            return name
    return None


def _get_or_create_person_dipreca(person, code, document, user):
    current = _get_person_dipreca(person)

    document_field = _dipreca_document_field()

    if not document_field:
        raise ValueError("El modelo PersonDiprecaCode no posee un campo de documento.")

    if current:
        setattr(current, document_field, document)
        _save_with_user(current, user)
        return current

    person_field = _dipreca_person_field()
    code_field = _dipreca_code_field()

    if not person_field or not code_field:
        raise ValueError("El modelo PersonDiprecaCode no posee los campos esperados.")

    code = str(code or "").strip()

    if not code:
        raise ValueError("Debe ingresar el código DIPRECA.")

    if PersonDiprecaCode.objects.filter(**{f"{code_field}__iexact": code}).exclude(
        **{person_field: person}
    ).exists():
        raise ValueError("El código DIPRECA ya se encuentra asociado a otra persona.")

    values = {
        person_field: person,
        code_field: code,
        document_field: document,
    }

    if _has_field(PersonDiprecaCode, "is_active"):
        values["is_active"] = True

    return _create_with_user(PersonDiprecaCode, user, **values)


# ============================================================
# MODAL ACCION
@login_required
@require_GET
def loan_action_modal(request, loan_id, action):
    loan = get_object_or_404(
        Loan.objects.select_related("person", "collection_method", "rate", "status"),
        pk=loan_id,
        is_active=True,
    )

    if _financial_operations_locked(loan) and action in FINANCIAL_ACTIONS:
        return render(
            request,
            "prestamos/portfolio/loan_action_modal.html",
            {
                "loan": loan,
                "action": action,
                "modal_error": (
                    "Este préstamo se encuentra transferido o recuperado y no admite "
                    "operaciones financieras. Las operaciones deben realizarse sobre "
                    "el préstamo vigente correspondiente."
                ),
            },
        )

    contribution_options = _contribution_options_for_loan(loan)
    total_contributions_available = sum(
        (Decimal(option["amount"] or 0) for option in contribution_options),
        Decimal("0"),
    )

    context = {
        "loan": loan,
        "action": action,
        "modal_error": "",
        "installment": None,
        "installments_no_collection": LoanInstallment.objects.none(),
        "contributions": _contributions_for_loan(loan),
        "contribution_options": contribution_options,
        "total_contributions_available": total_contributions_available,
        "external_methods": LoanPaymentExternalMethod.objects.filter(is_active=True).order_by("id"),
        "collection_methods": LoanCollectionMethod.objects.filter(is_active=True).exclude(pk=loan.collection_method_id),
        "rates": LoanRate.objects.filter(is_active=True).exclude(pk=loan.rate_id).order_by("name"),
        "document_types": DocumentType.objects.filter(is_active=True).order_by("name"),
        "minimum_prepayment": (Decimal(loan.principal_balance or 0) * Decimal("0.05")).quantize(MONEY),
        "overdue_count": 0,
        "overdue_principal": Decimal("0"),
        "overdue_interest": Decimal("0"),
        "overdue_total": Decimal("0"),
        "dipreca_code": "",
    }

    try:
        if action == "pay-installment":
            installment_id = int(request.GET.get("installment_id", 0))
            context["installment"] = get_object_or_404(
                LoanInstallment.objects.select_related("collection_method", "status"),
                pk=installment_id,
                loan=loan,
                is_active=True,
            )

        elif action == "no-collection":
            pending = _pending_installment_status()
            no_collection = _no_collection_status()

            context["installments_no_collection"] = (
                LoanInstallment.objects
                .filter(loan=loan, status__in=[pending, no_collection], is_active=True)
                .select_related("status", "collection_method")
                .order_by("installment_number")
            )
            context["no_collection_status_id"] = no_collection.id

        elif action == "overdue":
            first_day = timezone.localdate().replace(day=1)
            pending = _pending_installment_status()

            overdue = list(
                LoanInstallment.objects
                .filter(loan=loan, status=pending, due_date__lt=first_day, is_active=True)
                .order_by("installment_number")
            )

            context["overdue_installments"] = overdue
            context["overdue_count"] = len(overdue)
            context["overdue_principal"] = sum(
                (Decimal(item.principal or 0) for item in overdue),
                Decimal("0"),
            )
            context["overdue_interest"] = sum(
                (Decimal(item.interest or 0) for item in overdue),
                Decimal("0"),
            )
            context["overdue_total"] = sum(
                (Decimal(item.amount or 0) for item in overdue),
                Decimal("0"),
            )

        elif action == "collection-method":
            context["dipreca_code"] = str(_get_person_dipreca(loan.person) or "")

        elif action not in {
            "prepayment", "amortization", "insurance", "rate", "add-guarantor",
            "transfer-guarantors", "recover-guarantors", "document",
        }:
            raise ValueError("La acción seleccionada no existe.")

    except (ValueError, TypeError) as error:
        context["modal_error"] = str(error)

    return render(request, "prestamos/portfolio/loan_action_modal.html", context)


# ============================================================
# BUSCAR AVAL
@login_required
@require_GET
def guarantor_search(request, loan_id):
    loan = get_object_or_404(Loan, pk=loan_id, is_active=True)
    search = str(request.GET.get("q", "") or "").strip()

    if len(search) < 2:
        return JsonResponse({"status": "error", "message": "Ingrese al menos 2 caracteres."}, status=400)

    excluded = list(
        LoanGuarantor.objects.filter(loan=loan, is_active=True).values_list("person_id", flat=True)
    )
    excluded.append(loan.person_id)

    queryset = (
        Employee.objects
        .filter(is_active=True)
        .exclude(person_id__in=excluded)
        .select_related("person")
    )

    query = (
        Q(code__icontains=search)
        | Q(person__first_name__icontains=search)
        | Q(person__second_name__icontains=search)
        | Q(person__last_name_1__icontains=search)
        | Q(person__last_name_2__icontains=search)
        | Q(person__dv__icontains=search)
    )

    if search.isdigit():
        query |= Q(person__rut=int(search))

    queryset = queryset.filter(query).order_by("person__first_name", "person__last_name_1")[:30]

    return JsonResponse({
        "status": "ok",
        "results": [
            {
                "person_id": employee.person_id,
                "code": employee.code,
                "rut": _person_rut(employee.person),
                "name": _person_full_name(employee.person),
            }
            for employee in queryset
        ],
    })


# ============================================================
# DETALLE PAGO
@login_required
@require_GET
def payment_detail(request, loan_id, payment_id):
    loan = get_object_or_404(Loan, pk=loan_id, is_active=True)

    payment = get_object_or_404(
        LoanPayment.objects.select_related(
            "loan", "installment", "payment_type", "status", "user_create",
        ),
        pk=payment_id,
        loan=loan,
        is_active=True,
    )

    rows = []

    for external in (
        payment.external_payments
        .filter(is_active=True)
        .select_related("method", "contribution_type")
        .prefetch_related("documents__document")
        .order_by("id")
    ):
        relation = external.documents.filter(is_active=True).select_related("document").first()
        document = relation.document if relation else None
        number = (
            LoanDocumentNumber.objects
            .filter(document=document, is_active=True)
            .select_related("number_type")
            .order_by("id")
            .first()
            if document else None
        )

        rows.append({
            "method": external.method.name if external.method else "Extrasistema",
            "detail": str(external.contribution_type or ""),
            "amount": external.amount,
            "number": number.number if number else "",
            "document_url": _document_url(document),
        })

    for deposit in (
        payment.deposits
        .filter(is_active=True)
        .select_related("document")
        .order_by("id")
    ):
        number = (
            LoanDocumentNumber.objects
            .filter(document=deposit.document, is_active=True)
            .select_related("number_type")
            .order_by("id")
            .first()
            if deposit.document else None
        )

        rows.append({
            "method": "Depósito",
            "detail": "",
            "amount": deposit.amount,
            "number": number.number if number else "",
            "document_url": _document_url(deposit.document),
        })

    for contribution in (
        payment.contributions
        .filter(is_active=True)
        .select_related("contribution_type")
        .order_by("id")
    ):
        rows.append({
            "method": "Aporte",
            "detail": str(contribution.contribution_type),
            "amount": contribution.contribution_amount,
            "number": "",
            "document_url": "",
        })

    general_documents = [
        {"relation": relation, "url": _document_url(relation.document)}
        for relation in (
            payment.documents
            .filter(is_active=True)
            .select_related("document")
            .order_by("id")
        )
    ]

    reversal = (
        payment.reversals
        .filter(is_active=True)
        .select_related("document", "user_create")
        .order_by("-created_at")
        .first()
    )

    return render(
        request,
        "prestamos/portfolio/payment_detail_modal.html",
        {
            "loan": loan,
            "payment": payment,
            "rows": rows,
            "general_documents": general_documents,
            "reversal": reversal,
            "reversal_url": _document_url(reversal.document) if reversal else "",
            "payment_user": _user_name(payment.user_create),
        },
    )


# ============================================================
# POST ACCIONES
@login_required
@require_POST
def loan_action_post(request, loan_id, action):
    saved_paths = []

    try:
        with transaction.atomic():
            loan = get_object_or_404(
                Loan.objects
                .select_for_update()
                .select_related("person", "collection_method", "rate", "status"),
                pk=loan_id,
                is_active=True,
            )

            if _financial_operations_locked(loan) and action in FINANCIAL_ACTIONS:
                raise ValueError(
                    "Este préstamo se encuentra transferido o recuperado y no admite "
                    "operaciones financieras. Las operaciones deben realizarse sobre "
                    "el préstamo vigente correspondiente."
                )

            handlers = {
                "pay-installment": _post_pay_installment,
                "no-collection": _post_no_collection,
                "prepayment": _post_prepayment,
                "amortization": _post_amortization,
                "overdue": _post_overdue,
                "insurance": _post_insurance,
                "collection-method": _post_collection_method,
                "rate": _post_rate,
                "add-guarantor": _post_add_guarantor,
                "remove-guarantor": _post_remove_guarantor,
                "transfer-guarantors": _post_transfer_guarantors,
                "recover-guarantors": _post_recover_guarantors,
                "document": _post_document,
            }

            handler = handlers.get(action)

            if not handler:
                raise ValueError("La acción seleccionada no existe.")

            if action in {
                "pay-installment", "prepayment", "amortization", "insurance",
                "collection-method", "rate", "transfer-guarantors",
                "recover-guarantors", "document",
            }:
                message = handler(request, loan, saved_paths)
            else:
                message = handler(request, loan)

        return JsonResponse({"status": "ok", "message": message})

    except ValueError as error:
        for path_item in saved_paths:
            if default_storage.exists(path_item):
                default_storage.delete(path_item)

        return JsonResponse({"status": "error", "message": str(error)}, status=400)

    except Exception as error:
        for path_item in saved_paths:
            if default_storage.exists(path_item):
                default_storage.delete(path_item)

        return JsonResponse({
            "status": "error",
            "message": f"Error al procesar la operación: {error}",
        }, status=500)


# ============================================================
# PAGAR DIVIDENDO
def _post_pay_installment(request, loan, saved_paths):
    try:
        installment_id = int(request.POST.get("installment_id", 0) or 0)
    except (TypeError, ValueError):
        installment_id = 0

    installment = (
        LoanInstallment.objects
        .select_for_update()
        .select_related("status", "collection_method")
        .filter(pk=installment_id, loan=loan, is_active=True)
        .first()
    )

    if not installment:
        raise ValueError("No se encontró el dividendo.")

    if installment.status_id != _pending_installment_status().id:
        raise ValueError("El dividendo ya no se encuentra pendiente.")

    if not _collection_is_external(installment.collection_method):
        raise ValueError("Solo se pueden registrar pagos manuales para dividendos con cobro extrasistema.")

    previous = (
        LoanInstallment.objects
        .filter(
            loan=loan,
            installment_number__lt=installment.installment_number,
            is_active=True,
        )
        .select_related("status")
        .order_by("-installment_number")
        .first()
    )

    if previous and "pagad" not in _normalize(previous.status.name if previous.status else ""):
        raise ValueError("Debe pagarse primero el dividendo anterior.")

    if LoanPayment.objects.filter(
        installment=installment,
        status=_pending_payment_status(),
        is_active=True,
    ).exists():
        raise ValueError("Este dividendo ya posee una solicitud de pago pendiente.")

    modules = _parse_indexed_rows(request, "modules")

    if not modules:
        raise ValueError("Debe ingresar al menos un medio de pago.")

    total = Decimal("0")
    parsed = []
    used_deposit_numbers = set()
    deposit_number_type = _document_number_type("Número de Depósito", 1, request.user)
    current_year = timezone.localdate().year

    for row in modules:
        try:
            method_id = int(row["method"] or 0)
        except (TypeError, ValueError):
            method_id = 0

        method = LoanPaymentExternalMethod.objects.filter(pk=method_id, is_active=True).first()

        if not method:
            raise ValueError("Uno de los medios de pago no es válido.")

        amount = _decimal(row["amount"])

        if amount <= 0:
            raise ValueError("Todos los medios de pago deben tener un monto mayor a cero.")

        kind = _external_method_kind(method)
        contribution_type_id = None

        if kind == "contribution":
            try:
                contribution_type_id = int(row["contribution"] or 0)
            except (TypeError, ValueError):
                contribution_type_id = 0

            if contribution_type_id <= 0:
                raise ValueError("Debe seleccionar el tipo de aporte.")

            if amount > _available_contribution(contribution_type_id, loan):
                raise ValueError("El monto de aporte supera el saldo disponible.")

        if kind == "deposit":
            detail = str(row["detail"] or "").strip()

            if not detail.isdigit():
                raise ValueError("El número del depósito debe contener solamente números.")

            deposit_number = int(detail)

            if deposit_number in used_deposit_numbers:
                raise ValueError(
                    f"El número de depósito {deposit_number} está repetido en la misma operación."
                )

            _validate_document_number_unique(
                deposit_number_type,
                deposit_number,
                annual=True,
                year=current_year,
            )
            used_deposit_numbers.add(deposit_number)

            _validate_pdf(row["document"])

        parsed.append({
            "method": method,
            "amount": amount,
            "kind": kind,
            "contribution_type_id": contribution_type_id,
            "detail": str(row["detail"] or "").strip(),
            "document": row["document"],
        })

        total += amount

    expected = Decimal(installment.amount or 0).quantize(MONEY)

    if total.quantize(MONEY) != expected:
        raise ValueError("La suma de los medios de pago debe ser exactamente igual al monto del dividendo.")

    payment = _create_payment(
        request,
        loan,
        _payment_type(["Pago extrasistema", "Extrasistema", "Pago de dividendo"], 3),
        expected,
        installment=installment,
    )

    for row in parsed:
        external = _create_with_user(
            LoanPaymentExternal,
            request.user,
            payment=payment,
            amount=row["amount"],
            method=row["method"],
            contribution_type_id=row["contribution_type_id"] or None,
        )

        if row["document"]:
            document, route = _save_document(
                request,
                row["document"],
                loan,
                "payments",
                document_type_name="Comprobante de Pago de Préstamo",
            )
            saved_paths.append(route)

            _create_with_user(
                LoanPaymentExternalDocument,
                request.user,
                external_payment=external,
                document=document,
            )

            if row["detail"].isdigit():
                _create_with_user(
                    LoanDocumentNumber,
                    request.user,
                    document=document,
                    number_type=deposit_number_type,
                    number=int(row["detail"]),
                )

    installment.status = _pending_payment_installment_status()
    _save_with_user(installment, request.user)

    return "Solicitud de pago del dividendo registrada correctamente."


# ============================================================
# NO MANDAR A COBRO
def _post_no_collection(request, loan):
    pending = _pending_installment_status()
    no_collection = _no_collection_status()

    selected_ids = {
        int(value)
        for value in request.POST.getlist("installments")
        if str(value).isdigit()
    }

    candidates = list(
        LoanInstallment.objects
        .select_for_update()
        .filter(loan=loan, status__in=[pending, no_collection], is_active=True)
    )

    candidate_ids = {item.id for item in candidates}

    if not selected_ids.issubset(candidate_ids):
        raise ValueError("Se seleccionó un dividendo que no puede modificarse.")

    for installment in candidates:
        installment.status = no_collection if installment.id in selected_ids else pending
        _save_with_user(installment, request.user)

    return "Dividendos de no cobro actualizados correctamente."


# ============================================================
# PREPAGO
def _post_prepayment(request, loan, saved_paths):
    balance = Decimal(loan.principal_balance or 0)

    if balance <= 0:
        raise ValueError("El préstamo no posee saldo capital pendiente.")

    if LoanPayment.objects.filter(
        loan=loan,
        status=_pending_payment_status(),
        installment__isnull=False,
        is_active=True,
    ).exists():
        raise ValueError("Existen dividendos con solicitudes de pago pendientes.")

    deposits = _parse_indexed_rows(request, "deposits")

    if not deposits:
        raise ValueError("Debe ingresar al menos un depósito.")

    total = Decimal("0")
    parsed = []
    used_numbers = set()
    deposit_number_type = _document_number_type("Número de Depósito", 1, request.user)
    current_year = timezone.localdate().year

    for row in deposits:
        amount = _decimal(row["amount"])
        number = str(row["detail"] or "").strip()

        if amount <= 0:
            raise ValueError("El monto de cada depósito debe ser mayor a cero.")

        if not number.isdigit():
            raise ValueError("Cada depósito debe tener un número válido.")

        deposit_number = int(number)

        if deposit_number in used_numbers:
            raise ValueError(
                f"El número de depósito {deposit_number} está repetido en el mismo prepago."
            )

        _validate_document_number_unique(
            deposit_number_type,
            deposit_number,
            annual=True,
            year=current_year,
        )

        _validate_pdf(row["document"])

        used_numbers.add(deposit_number)
        total += amount
        parsed.append((amount, number, row["document"]))

    minimum = (balance * Decimal("0.05")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    if total < minimum:
        raise ValueError(f"El prepago debe ser al menos el 5% del saldo capital ({minimum}).")

    if total > balance:
        raise ValueError("El prepago no puede superar el saldo capital.")

    is_total = total.quantize(MONEY) == balance.quantize(MONEY)
    payment_type = _payment_type(
        ["Prepago total"] if is_total else ["Prepago parcial"],
        2 if is_total else 1,
    )

    payment = _create_payment(request, loan, payment_type, total)

    for amount, number, uploaded_file in parsed:
        document, route = _save_document(
            request,
            uploaded_file,
            loan,
            "prepayments",
            document_type_name="Comprobante de Prepago",
        )
        saved_paths.append(route)

        _create_with_user(
            LoanPaymentDeposit,
            request.user,
            payment=payment,
            amount=amount,
            document=document,
        )

        _create_with_user(
            LoanDocumentNumber,
            request.user,
            document=document,
            number_type=deposit_number_type,
            number=int(number),
        )

    return "Solicitud de prepago registrada correctamente."


# ============================================================
# AMORTIZACION
def _post_amortization(request, loan, saved_paths):
    balance = Decimal(loan.principal_balance or 0).quantize(MONEY)

    if balance <= 0:
        raise ValueError("El préstamo no posee saldo capital pendiente.")

    if LoanPayment.objects.filter(
        loan=loan,
        status=_pending_payment_status(),
        installment__isnull=False,
        is_active=True,
    ).exists():
        raise ValueError("Existen dividendos con solicitudes de pago pendientes.")

    contributions = _parse_contribution_amounts(request)

    if not contributions:
        raise ValueError("Debe utilizar al menos un aporte con saldo disponible.")

    available_by_type = {
        int(option["id"]): Decimal(option["amount"] or 0).quantize(MONEY)
        for option in _contribution_options_for_loan(loan)
    }

    total = Decimal("0")

    for contribution_type_id, contribution_amount in contributions:
        available = available_by_type.get(int(contribution_type_id), Decimal("0"))

        if available <= 0:
            raise ValueError("Uno de los aportes seleccionados no posee saldo disponible.")

        if contribution_amount > available:
            raise ValueError("Uno de los aportes supera el saldo disponible de la persona.")

        total += Decimal(contribution_amount or 0)

    amount = total.quantize(MONEY)

    if amount <= 0:
        raise ValueError("La suma de los aportes debe ser mayor a cero.")

    if amount > balance:
        raise ValueError("La suma de los aportes no puede superar el saldo capital del préstamo.")

    is_total = amount == balance
    payment_type = _payment_type(
        ["Amortización total"] if is_total else ["Amortización parcial"],
        5 if is_total else 4,
    )

    payment = _create_payment(request, loan, payment_type, amount)

    for contribution_type_id, contribution_amount in contributions:
        _create_with_user(
            LoanPaymentContribution,
            request.user,
            payment=payment,
            contribution_type_id=contribution_type_id,
            contribution_amount=contribution_amount,
            previous_contribution_balance=available_by_type[int(contribution_type_id)],
        )

    uploaded_file = request.FILES.get("document")
    resolution = str(request.POST.get("resolution", "") or "").strip()

    if uploaded_file:
        _validate_pdf(uploaded_file)

        document, route = _save_document(
            request,
            uploaded_file,
            loan,
            "amortizations",
            document_type_name="Resolución de Amortización",
        )
        saved_paths.append(route)

        _create_with_user(
            LoanPaymentDocument,
            request.user,
            payment=payment,
            document=document,
        )

        if resolution:
            if not resolution.isdigit():
                raise ValueError("El número de resolución debe contener solamente números.")

            resolution_number_type = _document_number_type("Número de Resolución", 2, request.user)
            resolution_number = int(resolution)
            _validate_document_number_unique(resolution_number_type, resolution_number)

            _create_with_user(
                LoanDocumentNumber,
                request.user,
                document=document,
                number_type=resolution_number_type,
                number=resolution_number,
            )

    elif resolution:
        raise ValueError("Si informa un número de resolución debe adjuntar el documento PDF.")

    return "Solicitud de amortización registrada correctamente."

# ============================================================
# AMORTIZACION DE INSOLUTOS
def _post_overdue(request, loan):
    first_day = timezone.localdate().replace(day=1)
    pending = _pending_installment_status()

    installments = list(
        LoanInstallment.objects
        .select_for_update()
        .filter(
            loan=loan,
            status=pending,
            due_date__lt=first_day,
            is_active=True,
        )
        .order_by("installment_number")
    )

    if not installments:
        raise ValueError("No existen dividendos insolutos pendientes.")

    amount = sum((Decimal(item.amount or 0) for item in installments), Decimal("0"))
    contributions = _parse_contribution_amounts(request)

    if not contributions:
        raise ValueError("Debe seleccionar aportes para amortizar los insolutos.")

    total = sum((value for _, value in contributions), Decimal("0"))

    if total.quantize(MONEY) != amount.quantize(MONEY):
        raise ValueError("La suma de aportes debe coincidir exactamente con el total insoluto.")

    available_by_type = {
        int(option["id"]): Decimal(option["amount"] or 0).quantize(MONEY)
        for option in _contribution_options_for_loan(loan)
    }

    for contribution_type_id, contribution_amount in contributions:
        available = available_by_type.get(int(contribution_type_id), Decimal("0"))

        if available <= 0:
            raise ValueError("Uno de los aportes seleccionados no posee saldo disponible.")

        if contribution_amount > available:
            raise ValueError("Uno de los aportes supera el saldo disponible de la persona.")

    payment = _create_payment(
        request,
        loan,
        _payment_type(["Amortización de insolutos", "Insolutos"], 8),
        amount,
    )

    for contribution_type_id, contribution_amount in contributions:
        _create_with_user(
            LoanPaymentContribution,
            request.user,
            payment=payment,
            contribution_type_id=contribution_type_id,
            contribution_amount=contribution_amount,
            previous_contribution_balance=available_by_type[int(contribution_type_id)],
        )

    new_status = _pending_amortization_status()

    for installment in installments:
        installment.status = new_status
        _save_with_user(installment, request.user)

    return "Solicitud de amortización de insolutos registrada correctamente."


# ============================================================
# DESGRAVAMEN
def _post_insurance(request, loan, saved_paths):
    amount = _decimal(request.POST.get("amount"), "Monto de desgravamen")

    if amount <= 0:
        raise ValueError("Debe indicar un monto de desgravamen mayor a cero.")

    if amount > Decimal(loan.principal_balance or 0):
        raise ValueError("El desgravamen no puede superar el saldo capital.")

    uploaded_file = request.FILES.get("document")
    _validate_pdf(uploaded_file)

    payment = _create_payment(
        request,
        loan,
        _payment_type(["Desgravamen"], 7),
        amount,
    )

    document, route = _save_document(
        request,
        uploaded_file,
        loan,
        "insurance",
        document_type_name="Documento de Desgravamen",
    )
    saved_paths.append(route)

    _create_with_user(
        LoanPaymentDocument,
        request.user,
        payment=payment,
        document=document,
    )

    return "Solicitud de desgravamen registrada correctamente."


# ============================================================
# CAMBIO METODO DE COBRO
def _post_collection_method(request, loan, saved_paths):
    try:
        method_id = int(request.POST.get("collection_method", 0) or 0)
    except (TypeError, ValueError):
        method_id = 0

    method = LoanCollectionMethod.objects.filter(pk=method_id, is_active=True).first()

    if not method:
        raise ValueError("Debe seleccionar un método de cobro válido.")

    if method.id == loan.collection_method_id:
        raise ValueError("Debe seleccionar un método de cobro diferente al actual.")

    apply_from = str(request.POST.get("apply_from", "") or "").strip()

    if apply_from == "actual":
        months = 0

    elif apply_from == "siguiente":
        months = 1

    elif apply_from == "x_meses":
        try:
            months = int(request.POST.get("months", 0) or 0)
        except (TypeError, ValueError):
            months = 0

        if months < 2:
            raise ValueError("La cantidad de meses debe ser al menos 2.")

    else:
        raise ValueError("Debe indicar desde qué mes se aplicará el cambio.")

    # --------------------------------------------------------
    # DOCUMENTO RESPALDO
    uploaded_file = request.FILES.get("document")
    _validate_pdf(uploaded_file)

    document, route = _save_document(
        request,
        uploaded_file,
        loan,
        "collection-method",
        document_type_name="Cambio de Método de Cobro",
    )
    saved_paths.append(route)

    # --------------------------------------------------------
    # CODIGO DIPRECA
    dipreca = None

    if "dipreca" in _normalize(method.name):
        dipreca = _get_or_create_person_dipreca(
            person=loan.person,
            code=request.POST.get("dipreca_code", ""),
            document=document,
            user=request.user,
        )

    # --------------------------------------------------------
    # HISTORIAL CAMBIO METODO
    _create_with_user(
        LoanCollectionMethodRecord,
        request.user,
        collection_method=method,
        document=document,
        loan=loan,
        dipreca_code=dipreca,
        ip=_get_client_ip(request),
    )

    # --------------------------------------------------------
    # ACTUALIZAR PRESTAMO
    loan.collection_method = method
    _save_with_user(loan, request.user)

    # --------------------------------------------------------
    # ACTUALIZAR DIVIDENDOS DESDE LA FECHA SELECCIONADA
    target_date = _first_day_after_months(months)
    pending = _pending_installment_status()

    installments = (
        LoanInstallment.objects
        .select_for_update()
        .filter(
            loan=loan,
            status=pending,
            due_date__gte=target_date,
            is_active=True,
        )
    )

    for installment in installments:
        installment.collection_method = method
        _save_with_user(installment, request.user)

    return "Método de cobro actualizado correctamente."


# ============================================================
# CAMBIO TASA
def _post_rate(request, loan, saved_paths):
    try:
        rate_id = int(request.POST.get("rate", 0) or 0)
    except (TypeError, ValueError):
        rate_id = 0

    new_rate = LoanRate.objects.filter(pk=rate_id, is_active=True).first()

    if not new_rate:
        raise ValueError("Debe seleccionar una tasa válida.")

    if new_rate.id == loan.rate_id:
        raise ValueError("Debe seleccionar una tasa diferente a la actual.")

    uploaded_file = request.FILES.get("document")
    _validate_pdf(uploaded_file)

    document, route = _save_document(
        request,
        uploaded_file,
        loan,
        "rates",
        document_type_name="Cambio de Tasa de Préstamo",
    )
    saved_paths.append(route)

    previous_rate = loan.rate

    _create_with_user(
        LoanRateRecord,
        request.user,
        loan=loan,
        previous_rate=previous_rate,
        new_rate=new_rate,
        document=document,
        ip=_get_client_ip(request),
    )

    loan.rate = new_rate
    _save_with_user(loan, request.user)

    _recalculate_pending_installments(loan, request.user)

    return "Tasa actualizada y dividendos pendientes recalculados correctamente."


# ============================================================
# AGREGAR AVAL
def _post_add_guarantor(request, loan):
    try:
        person_id = int(request.POST.get("person_id", 0) or 0)
    except (TypeError, ValueError):
        person_id = 0

    if person_id <= 0:
        raise ValueError("Debe seleccionar un aval.")

    if person_id == loan.person_id:
        raise ValueError("El titular del préstamo no puede ser su propio aval.")

    person = Person.objects.filter(pk=person_id, is_active=True).first()

    if not person:
        raise ValueError("La persona seleccionada no existe.")

    relation = LoanGuarantor.objects.filter(loan=loan, person=person).first()

    if relation:
        if relation.is_active:
            raise ValueError("La persona ya se encuentra registrada como aval.")

        relation.is_active = True
        _save_with_user(relation, request.user)
    else:
        _create_with_user(
            LoanGuarantor,
            request.user,
            loan=loan,
            person=person,
        )

    return "Aval agregado correctamente."


# ============================================================
# QUITAR AVAL
def _post_remove_guarantor(request, loan):
    try:
        relation_id = int(request.POST.get("relation_id", 0) or 0)
    except (TypeError, ValueError):
        relation_id = 0

    relation = (
        LoanGuarantor.objects
        .select_for_update()
        .filter(pk=relation_id, loan=loan, is_active=True)
        .first()
    )

    if not relation:
        raise ValueError("No se encontró el aval.")

    if Loan.objects.filter(
        previous_loan=loan,
        person_id=relation.person_id,
        is_active=True,
    ).exclude(status__name__icontains="Recuper").exists():
        raise ValueError("No puede quitar un aval que posee un préstamo transferido activo.")

    relation.is_active = False
    _save_with_user(relation, request.user)

    return "Aval eliminado correctamente."


# ============================================================
# TRANSFERIR A AVALES
def _post_transfer_guarantors(request, loan, saved_paths):
    guarantors = list(
        LoanGuarantor.objects
        .select_for_update()
        .filter(loan=loan, is_active=True)
        .select_related("person")
        .order_by("id")
    )

    if not guarantors:
        raise ValueError("El préstamo no posee avales activos.")

    balance = Decimal(loan.principal_balance or 0)

    if balance <= 0:
        raise ValueError("El préstamo no posee saldo capital para transferir.")

    if Loan.objects.filter(previous_loan=loan, is_active=True).exclude(
        status__name__icontains="Recuper"
    ).exists():
        raise ValueError("El préstamo ya posee préstamos hijos activos.")

    observation_text = str(request.POST.get("observation", "") or "").strip()

    if len(observation_text) < 5:
        raise ValueError("Debe ingresar una observación para la transferencia.")

    uploaded_file = request.FILES.get("document")
    _validate_pdf(uploaded_file)

    document, route = _save_document(
        request,
        uploaded_file,
        loan,
        "guarantors",
        document_type_name="Resolución de Transferencia a Avales",
    )
    saved_paths.append(route)

    observation = _create_observation(request, observation_text)

    _create_with_user(
        LoanGuarantorMovement,
        request.user,
        original_loan=loan,
        movement_type=1,
        observation=observation,
        document=document,
    )

    child_status = _loan_status(["Vigente", "Activo"], 1)
    transferred_status = _loan_status(["Transferido", "Transferido a avales"], 4)

    default_collection = (
        LoanCollectionMethod.objects
        .filter(is_active=True)
        .filter(Q(name__icontains="remuner") | Q(name__icontains="sueldo"))
        .order_by("id")
        .first()
        or LoanCollectionMethod.objects.filter(pk=1, is_active=True).first()
        or loan.collection_method
    )

    count = len(guarantors)
    base_share = (balance / Decimal(count)).quantize(MONEY, rounding=ROUND_HALF_UP)
    assigned = Decimal("0")

    for index, guarantor in enumerate(guarantors, start=1):
        share = balance - assigned if index == count else base_share
        assigned += share

        child = _create_with_user(
            Loan,
            request.user,
            request=loan.request,
            loan_type=loan.loan_type,
            type_concept=loan.type_concept,
            person=guarantor.person,
            collection_method=default_collection,
            rate=loan.rate,
            unique_code="",
            loan_amount=share,
            interest_amount=0,
            principal_balance=share,
            interest_balance=0,
            term=loan.term,
            installments_paid=0,
            principal_paid=0,
            interest_paid=0,
            start_date=loan.start_date,
            end_date=loan.end_date,
            is_mortgage=loan.is_mortgage,
            status=child_status,
            previous_loan=loan,
        )

        _create_child_installments(loan, child, request.user)

    loan.status = transferred_status
    _save_with_user(loan, request.user)

    return "Préstamo transferido correctamente a los avales."


# ============================================================
# RECUPERAR DESDE AVALES
def _post_recover_guarantors(request, loan, saved_paths):
    transferred_status = _loan_status(["Transferido", "Transferido a avales"], 4)

    if loan.status_id != transferred_status.id:
        raise ValueError("El préstamo original no se encuentra en estado transferido.")

    children = list(
        Loan.objects
        .select_for_update()
        .filter(previous_loan=loan, is_active=True)
        .exclude(status__name__icontains="Recuper")
        .order_by("id")
    )

    if not children:
        raise ValueError("No existen préstamos hijos activos para recuperar.")

    observation_text = str(request.POST.get("observation", "") or "").strip()

    if len(observation_text) < 5:
        raise ValueError("Debe ingresar una observación para la recuperación.")

    uploaded_file = request.FILES.get("document")
    _validate_pdf(uploaded_file)

    document, route = _save_document(
        request,
        uploaded_file,
        loan,
        "guarantors",
        document_type_name="Resolución de Recuperación desde Avales",
    )
    saved_paths.append(route)

    observation = _create_observation(request, observation_text)

    _create_with_user(
        LoanGuarantorMovement,
        request.user,
        original_loan=loan,
        movement_type=2,
        observation=observation,
        document=document,
    )

    loan.principal_balance = sum(
        (Decimal(child.principal_balance or 0) for child in children),
        Decimal("0"),
    )
    loan.status = _loan_status(["Vigente", "Activo"], 1)
    _save_with_user(loan, request.user)

    recovered_status = _loan_status(["Recuperado"], 5)

    for child in children:
        child.status = recovered_status
        _save_with_user(child, request.user)

    return "Préstamos recuperados correctamente desde los avales."


# ============================================================
# DOCUMENTO PRESTAMO
def _post_document(request, loan, saved_paths):
    try:
        document_type_id = int(request.POST.get("document_type", 0) or 0)
    except (TypeError, ValueError):
        document_type_id = 0

    document_type = DocumentType.objects.filter(pk=document_type_id, is_active=True).first()

    if not document_type:
        raise ValueError("Debe seleccionar un tipo de documento.")

    uploaded_file = request.FILES.get("document")
    _validate_pdf(uploaded_file)

    document, route = _save_document(
        request,
        uploaded_file,
        loan,
        "documents",
        document_type=document_type,
    )
    saved_paths.append(route)

    _create_with_user(
        LoanDocument,
        request.user,
        loan=loan,
        document=document,
        document_type=document_type,
    )

    return "Documento adjuntado correctamente."
