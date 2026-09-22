import math
import unicodedata
import uuid

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models.document import Document, DocumentType
from core.models.employee import Employee
from core.models.partner import (
    Partner,
    PartnerContribution,
    PartnerMovement,
    PartnerMovementType,
)

from ..models.loan import (
    Loan,
    LoanCollectionMethod,
    LoanInstallment,
    LoanInstallmentStatus,
    LoanStatus,
)
from ..models.payment import (
    LoanDocumentNumber,
    LoanDocumentNumberType,
    LoanPayment,
    LoanPaymentContribution,
    LoanPaymentDeposit,
    LoanPaymentDocument,
    LoanPaymentExternal,
    LoanPaymentExternalDocument,
    LoanPaymentReversal,
    LoanPaymentStatus,
)


MAX_FILE_SIZE = 10 * 1024 * 1024
MONEY = Decimal("0.01")


# ============================================================
# UTILIDADES GENERALES
def _normalize(value):
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    return "".join(character for character in value if not unicodedata.combining(character))


def _person_full_name(person):
    if not person:
        return ""

    values = [
        getattr(person, "first_name", ""),
        getattr(person, "second_name", ""),
        getattr(person, "last_name_1", ""),
        getattr(person, "last_name_2", ""),
    ]

    return " ".join(str(value).strip() for value in values if value)


def _person_rut(person):
    if not person:
        return ""

    return f"{getattr(person, 'rut', '')}-{getattr(person, 'dv', '')}"


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR") or "127.0.0.1"


def _format_datetime(value):
    if not value:
        return ""

    if timezone.is_aware(value):
        value = timezone.localtime(value)

    return value.strftime("%d-%m-%Y %H:%M")


def _decimal(value, field_name="Monto"):
    try:
        normalized = str(value or "0").strip().replace(".", "").replace(",", ".")
        return Decimal(normalized)
    except Exception:
        raise ValueError(f"{field_name} inválido.")


def _save_with_user(instance, audit_user):
    instance.save(user=audit_user)
    return instance


def _create_with_user(model, audit_user, **values):
    instance = model(**values)
    instance.save(user=audit_user)
    return instance


def _reference(model, aliases, fallback_id=None):
    aliases = [_normalize(alias) for alias in aliases if alias]

    for item in model.objects.filter(is_active=True).order_by("id"):
        if _normalize(getattr(item, "name", "")) in aliases:
            return item

    if fallback_id:
        item = model.objects.filter(pk=fallback_id, is_active=True).first()

        if item:
            return item

    raise ValueError(
        f"No existe un registro activo de {model._meta.verbose_name} "
        f"para: {', '.join(aliases)}."
    )


# ============================================================
# ESTADOS
def _payment_pending():
    return _reference(LoanPaymentStatus, ["Pendiente", "Pending"], 1)


def _payment_approved():
    return _reference(LoanPaymentStatus, ["Aprobado", "Aprobada", "Approved"], 2)


def _payment_rejected():
    return _reference(LoanPaymentStatus, ["Rechazado", "Rechazada", "Rejected"], 3)


def _payment_reversed():
    return _reference(LoanPaymentStatus, ["Reversado", "Reversada", "Reversed"], 4)


def _payment_pending_reversal():
    return _reference(
        LoanPaymentStatus,
        ["Pendiente reversa", "Pendiente de reversa", "Pending reversal"],
        5,
    )


def _latest_reversible_payment_id(loan_id):
    """Retorna el último pago efectivo del préstamo que puede participar en una reversa.

    Un pago pendiente de reversa sigue siendo el último pago hasta que la solicitud
    sea aprobada o rechazada. Así no se habilita el pago anterior mientras existe
    una reversa pendiente sobre el último pago.
    """
    approved = _payment_approved()
    pending_reversal = _payment_pending_reversal()

    return (
        LoanPayment.objects
        .filter(loan_id=loan_id, status__in=[approved, pending_reversal], is_active=True)
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    )


def _installment_pending():
    return _reference(LoanInstallmentStatus, ["Pendiente", "Pending"], 1)


def _installment_paid():
    return _reference(LoanInstallmentStatus, ["Pagado", "Pagada", "Paid"], 2)


def _installment_pending_payment():
    return _reference(
        LoanInstallmentStatus,
        ["Solicitud de pago", "Pago pendiente", "Pendiente aprobación pago"],
        8,
    )


def _installment_pending_amortization():
    return _reference(
        LoanInstallmentStatus,
        ["Por amortizar", "Pendiente amortización"],
        5,
    )


def _loan_active_status():
    return _reference(
        LoanStatus,
        ["Vigente", "Activo", "Activa", "En curso", "Active"],
        1,
    )


def _loan_paid_status():
    return _reference(
        LoanStatus,
        ["Pagado", "Pagada", "Finalizado", "Finalizada", "Paid"],
        2,
    )


def _amortized_collection_method():
    try:
        return _reference(
            LoanCollectionMethod,
            ["Amortizado", "Amortizada", "Amortización", "Amortizacion"],
            6,
        )
    except ValueError:
        return None


# ============================================================
# CLASIFICACIÓN DEL PAGO
def _payment_kind(payment):
    payment_type_id = int(payment.payment_type_id or 0)
    name = _normalize(payment.payment_type.name if payment.payment_type else "")

    is_external = payment_type_id == 3 or "extrasistema" in name or ("extra" in name and "sistema" in name)
    is_prepayment = payment_type_id in {1, 2} or "prepago" in name
    is_insurance = payment_type_id == 7 or "desgravamen" in name
    is_insolvent = payment_type_id == 8 or "insolut" in name
    is_amortization = payment_type_id in {4, 5} or ("amortiz" in name and not is_insolvent)

    return {
        "name": name,
        "external": is_external,
        "prepayment": is_prepayment,
        "insurance": is_insurance,
        "amortization": is_amortization,
        "insolvent": is_insolvent,
    }

# ============================================================
# SOCIO / APORTES / MOVIMIENTOS
def _partner_for_loan(loan):
    return (
        Partner.objects
        .filter(person_id=loan.person_id, is_active=True)
        .order_by("-id")
        .first()
    )


def _movement_type(aliases, fallback_id):
    return _reference(PartnerMovementType, aliases, fallback_id)


def _next_movement_number(partner):
    value = (
        PartnerMovement.objects
        .filter(partner=partner)
        .aggregate(maximum=Max("movement_number"))["maximum"]
        or 0
    )
    return int(value) + 1


def _register_partner_movement(partner, contribution_type, amount, description, movement_type, user):
    _create_with_user(
        PartnerMovement,
        user,
        movement_type=movement_type,
        partner=partner,
        contribution_type=contribution_type,
        movement_number=_next_movement_number(partner),
        description=description,
        amount=amount,
    )


def _change_contribution_balance(loan, contribution_type, amount, increase, description, movement_aliases, fallback_id, user):
    partner = _partner_for_loan(loan)

    if not partner:
        raise ValueError("No se encontró el socio asociado al préstamo.")

    contribution = (
        PartnerContribution.objects
        .select_for_update()
        .filter(
            partner=partner,
            contribution_type=contribution_type,
            is_active=True,
        )
        .order_by("-id")
        .first()
    )

    if not contribution:
        raise ValueError(
            f"El socio no posee el aporte {contribution_type}."
        )

    amount = Decimal(amount or 0)

    if amount <= 0:
        return

    current = Decimal(contribution.amount or 0)

    if increase:
        contribution.amount = current + amount
    else:
        if amount > current:
            raise ValueError(
                f"El saldo del aporte {contribution_type} es insuficiente."
            )

        contribution.amount = current - amount

    _save_with_user(contribution, user)

    _register_partner_movement(
        partner=partner,
        contribution_type=contribution_type,
        amount=amount,
        description=description,
        movement_type=_movement_type(movement_aliases, fallback_id),
        user=user,
    )


def _deduct_amortization_contributions(payment, user):
    for row in (
        LoanPaymentContribution.objects
        .select_for_update()
        .filter(payment=payment, is_active=True)
        .select_related("contribution_type")
    ):
        _change_contribution_balance(
            loan=payment.loan,
            contribution_type=row.contribution_type,
            amount=row.contribution_amount,
            increase=False,
            description=f"giro amortización pago #{payment.id}",
            movement_aliases=["Giro", "Retiro"],
            fallback_id=1,
            user=user,
        )


def _restore_amortization_contributions(payment, user):
    for row in (
        LoanPaymentContribution.objects
        .select_for_update()
        .filter(payment=payment, is_active=True)
        .select_related("contribution_type")
    ):
        _change_contribution_balance(
            loan=payment.loan,
            contribution_type=row.contribution_type,
            amount=row.contribution_amount,
            increase=True,
            description=f"reversa giro amortización pago #{payment.id}",
            movement_aliases=["Giro", "Retiro"],
            fallback_id=1,
            user=user,
        )


def _deduct_external_contributions(payment, user):
    for row in (
        LoanPaymentExternal.objects
        .select_for_update()
        .filter(
            payment=payment,
            contribution_type__isnull=False,
            is_active=True,
        )
        .select_related("contribution_type")
    ):
        _change_contribution_balance(
            loan=payment.loan,
            contribution_type=row.contribution_type,
            amount=row.amount,
            increase=False,
            description=f"giro pago cuota #{payment.installment.installment_number if payment.installment else '-'}",
            movement_aliases=["Giro", "Retiro"],
            fallback_id=1,
            user=user,
        )


def _restore_external_contributions(payment, user):
    for row in (
        LoanPaymentExternal.objects
        .select_for_update()
        .filter(
            payment=payment,
            contribution_type__isnull=False,
            is_active=True,
        )
        .select_related("contribution_type")
    ):
        _change_contribution_balance(
            loan=payment.loan,
            contribution_type=row.contribution_type,
            amount=row.amount,
            increase=True,
            description=f"reversa giro extrasistema pago #{payment.id}",
            movement_aliases=["Giro", "Retiro"],
            fallback_id=1,
            user=user,
        )


def _deposit_origin_amount(payment):
    deposits = (
        LoanPaymentDeposit.objects
        .filter(payment=payment, is_active=True)
        .values_list("amount", flat=True)
    )

    external_deposits = (
        LoanPaymentExternal.objects
        .filter(
            payment=payment,
            contribution_type__isnull=True,
            is_active=True,
        )
        .values_list("amount", flat=True)
    )

    total = sum((Decimal(value or 0) for value in deposits), Decimal("0"))
    total += sum((Decimal(value or 0) for value in external_deposits), Decimal("0"))

    return total


def _send_reversal_deposit_to_contribution(payment, reversal, user):
    amount = _deposit_origin_amount(payment)

    if amount <= 0:
        return

    if not reversal.deposit_contribution_type_id:
        raise ValueError(
            "La reversa no posee un aporte de destino para el dinero proveniente de depósito."
        )

    _change_contribution_balance(
        loan=payment.loan,
        contribution_type=reversal.deposit_contribution_type,
        amount=amount,
        increase=True,
        description=f"depósito por reversa pago #{payment.id}",
        movement_aliases=["Depósito", "Deposito", "Ingreso"],
        fallback_id=2,
        user=user,
    )


# ============================================================
# DOCUMENTOS
def _validate_pdf(uploaded_file):
    if not uploaded_file:
        raise ValueError("Debe adjuntar un documento PDF.")

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError("El documento no puede superar los 10 MB.")

    extension = Path(uploaded_file.name).suffix.lower()

    if extension != ".pdf":
        raise ValueError("El documento debe estar en formato PDF.")


def _document_type(name, user):
    item = (
        DocumentType.objects
        .filter(name__iexact=name, is_active=True)
        .order_by("id")
        .first()
    )

    if item:
        return item

    return _create_with_user(DocumentType, user, name=name)


def _document_number_type(name, fallback_id, user):
    try:
        return _reference(LoanDocumentNumberType, [name], fallback_id)
    except ValueError:
        return _create_with_user(LoanDocumentNumberType, user, name=name)


def _save_document(request, uploaded_file, payment, folder, document_type_name):
    _validate_pdf(uploaded_file)

    extension = Path(uploaded_file.name).suffix.lower()
    internal_name = f"{uuid.uuid4().hex}{extension}"
    relative_path = (
        Path("loans")
        / str(payment.loan_id)
        / "payment-manager"
        / str(payment.id)
        / folder
        / internal_name
    )

    stored_path = default_storage.save(str(relative_path), uploaded_file)

    document = _create_with_user(
        Document,
        request.user,
        user=request.user,
        type_document=_document_type(document_type_name, request.user),
        ip=_get_client_ip(request),
        size=uploaded_file.size,
        document_name=uploaded_file.name,
        internal_name=internal_name,
        file_type=uploaded_file.content_type or "application/pdf",
        route=stored_path,
    )

    return document, stored_path


# ============================================================
# FECHAS / TABLA FRANCESA
def _month_end(value):
    return value.replace(day=monthrange(value.year, value.month)[1])


def _add_months(value, months):
    index = value.year * 12 + value.month - 1 + months
    year = index // 12
    month = index % 12 + 1
    return date(year, month, 1)


def _french_schedule(principal, annual_rate_percent, periods):
    principal = Decimal(principal or 0)
    annual_rate_percent = Decimal(annual_rate_percent or 0)
    periods = int(periods or 0)

    if principal <= 0 or periods <= 0:
        return []

    annual = annual_rate_percent / Decimal("100")
    monthly = Decimal(str(math.pow(float(Decimal("1") + annual), 1 / 12) - 1))
    monthly = monthly.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    balance_exact = principal
    rows = []
    principal_accumulated = Decimal("0")

    if monthly <= 0:
        installment_exact = principal / Decimal(periods)
        installment_saved = installment_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        for number in range(1, periods + 1):
            interest_saved = Decimal("0")

            if number < periods:
                principal_saved = installment_saved
                amount_saved = installment_saved
            else:
                principal_saved = (principal - principal_accumulated).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
                amount_saved = principal_saved

            principal_accumulated += principal_saved

            rows.append({
                "amount": amount_saved.quantize(MONEY),
                "principal": principal_saved.quantize(MONEY),
                "interest": interest_saved.quantize(MONEY),
            })

        return rows

    installment_exact = (
        principal
        * monthly
        / (Decimal("1") - (Decimal("1") + monthly) ** Decimal(-periods))
    )
    installment_saved = installment_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    for number in range(1, periods + 1):
        interest_exact = balance_exact * monthly
        interest_saved = interest_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        if number < periods:
            principal_saved = installment_saved - interest_saved

            if principal_saved < 0:
                principal_saved = Decimal("0")

            amount_saved = installment_saved
        else:
            principal_saved = (principal - principal_accumulated).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
            amount_saved = principal_saved + interest_saved

        principal_accumulated += principal_saved

        if number < periods:
            principal_exact = installment_exact - interest_exact
            balance_exact -= principal_exact
        else:
            balance_exact = Decimal("0")

        rows.append({
            "amount": amount_saved.quantize(MONEY),
            "principal": principal_saved.quantize(MONEY),
            "interest": interest_saved.quantize(MONEY),
        })

    return rows


def _recalculate_installments(loan, months_from_current, user):
    months_from_current = max(int(months_from_current or 0), 0)

    paid = _installment_paid()
    pending = _installment_pending()
    current_first_day = timezone.localdate().replace(day=1)
    cutoff = _add_months(current_first_day, months_from_current)

    installments = list(
        LoanInstallment.objects
        .select_for_update()
        .filter(loan=loan)
        .select_related("status")
        .order_by("installment_number", "id")
    )

    # ============================================================
    # DETERMINAR ULTIMO DIVIDENDO QUE SE MANTIENE
    kept = [
        installment
        for installment in installments
        if installment.is_active
        and (
            installment.due_date < cutoff
            or installment.status_id == paid.id
        )
    ]

    last_kept = max(
        kept,
        key=lambda item: (item.installment_number, item.due_date, item.id),
        default=None,
    )

    last_number = int(last_kept.installment_number or 0) if last_kept else 0
    first_due_date = _month_end(cutoff)

    if last_kept:
        first_due_date = _month_end(_add_months(last_kept.due_date, 1))

    remaining_periods = max(int(loan.term or 0) - last_number, 0)
    balance = max(Decimal("0"), Decimal(loan.principal_balance or 0))

    # ============================================================
    # DIVIDENDOS FUTUROS NO PAGADOS
    future_non_paid = [
        installment
        for installment in installments
        if installment.is_active
        and installment.due_date >= cutoff
        and installment.status_id != paid.id
    ]

    # ============================================================
    # PREPAGO / AMORTIZACION TOTAL O SIN CUOTAS RESTANTES
    if balance <= 0 or remaining_periods <= 0:
        for installment in future_non_paid:
            installment.is_active = False
            _save_with_user(installment, user)

        active_interest = sum(
            (
                Decimal(item.interest or 0)
                for item in LoanInstallment.objects
                .filter(loan=loan, is_active=True)
                .exclude(status=paid)
            ),
            Decimal("0"),
        )

        loan.interest_balance = active_interest
        loan.interest_amount = Decimal(loan.interest_paid or 0) + active_interest
        _save_with_user(loan, user)
        return 0

    # ============================================================
    # GENERAR NUEVA TABLA FRANCESA
    rate_value = Decimal(getattr(loan.rate, "rate", 0) or 0)

    if rate_value <= 0:
        raise ValueError("La tasa del préstamo es inválida para recalcular dividendos.")

    schedule = _french_schedule(balance, rate_value, remaining_periods)

    if not schedule:
        raise ValueError("No fue posible generar los dividendos recalculados.")

    # ============================================================
    # REUTILIZAR REGISTROS EXISTENTES POR NUMERO DE CUOTA
    by_number = {
        int(installment.installment_number): installment
        for installment in installments
    }

    generated_numbers = set()

    for index, row in enumerate(schedule):
        number = last_number + index + 1
        due_date = _month_end(_add_months(first_due_date, index))
        generated_numbers.add(number)

        installment = by_number.get(number)

        if installment and installment.status_id == paid.id:
            raise ValueError(
                f"No se puede recalcular la cuota {number} porque se encuentra pagada."
            )

        if installment:
            installment.collection_method = loan.collection_method
            installment.status = pending
            installment.due_date = due_date
            installment.amount = row["amount"]
            installment.principal = row["principal"]
            installment.interest = row["interest"]
            installment.installment_number = number
            installment.is_active = True
            _save_with_user(installment, user)
        else:
            installment = _create_with_user(
                LoanInstallment,
                user,
                loan=loan,
                collection_method=loan.collection_method,
                status=pending,
                due_date=due_date,
                amount=row["amount"],
                principal=row["principal"],
                interest=row["interest"],
                installment_number=number,
                is_active=True,
            )
            by_number[number] = installment

    # ============================================================
    # DESACTIVAR DIVIDENDOS FUTUROS QUE YA NO CORRESPONDEN
    for installment in future_non_paid:
        number = int(installment.installment_number or 0)

        if number not in generated_numbers:
            installment.is_active = False
            _save_with_user(installment, user)

    # ============================================================
    # ACTUALIZAR INTERESES DEL PRESTAMO
    active_non_paid_interest = sum(
        (
            Decimal(item.interest or 0)
            for item in LoanInstallment.objects
            .filter(loan=loan, is_active=True)
            .exclude(status=paid)
        ),
        Decimal("0"),
    )

    loan.interest_balance = active_non_paid_interest
    loan.interest_amount = Decimal(loan.interest_paid or 0) + active_non_paid_interest
    _save_with_user(loan, user)

    # ============================================================
    # VERIFICAR QUE EL RECALCULO QUEDO GUARDADO
    first_number = last_number + 1
    first_row = LoanInstallment.objects.filter(
        loan=loan,
        installment_number=first_number,
        is_active=True,
    ).first()

    if not first_row:
        raise ValueError("El recálculo se ejecutó, pero no se pudo verificar el primer dividendo generado.")

    expected = schedule[0]

    if (
        Decimal(first_row.amount or 0).quantize(MONEY) != Decimal(expected["amount"]).quantize(MONEY)
        or Decimal(first_row.principal or 0).quantize(MONEY) != Decimal(expected["principal"]).quantize(MONEY)
        or Decimal(first_row.interest or 0).quantize(MONEY) != Decimal(expected["interest"]).quantize(MONEY)
    ):
        raise ValueError("Los dividendos recalculados no quedaron persistidos correctamente.")

    return len(schedule)

# ============================================================
# OBTENER INICIO DE RECALCULO
def _recalc_months_from_request(request, required):
    value = str(
        request.POST.get("recalculation_start")
        or request.POST.get("recalculo_inicio")
        or ""
    ).strip()

    raw_months = (
        request.POST.get("recalculation_months")
        or request.POST.get("recalculo_meses")
        or 0
    )

    try:
        months = int(raw_months or 0)
    except (TypeError, ValueError):
        months = 0

    aliases = {
        "current": "current",
        "actual": "current",
        "next": "next",
        "siguiente": "next",
        "months": "months",
        "x_meses": "months",
    }

    value = aliases.get(value, value)

    if not value:
        if required:
            raise ValueError("Debe seleccionar desde cuándo se recalcularán los dividendos.")

        return 0

    if value == "current":
        return 0

    if value == "next":
        return 1

    if value == "months":
        if months < 2:
            raise ValueError("La cantidad de meses debe ser mayor o igual a 2.")

        return months

    raise ValueError("La opción de recálculo seleccionada no es válida.")

# ============================================================
# ESTADO FINAL DEL PRÉSTAMO
def _sync_installments_paid(loan, user):
    paid = _installment_paid()

    total_paid = (
        LoanInstallment.objects
        .filter(
            loan=loan,
            status=paid,
            is_active=True,
        )
        .count()
    )

    loan.installments_paid = total_paid
    _save_with_user(loan, user)

    return total_paid


def _update_loan_paid_status(loan, user):
    if Decimal(loan.principal_balance or 0) <= 0:
        loan.principal_balance = Decimal("0")
        loan.status = _loan_paid_status()
    elif _normalize(loan.status.name if loan.status else "") in {
        "pagado",
        "pagada",
        "paid",
        "finalizado",
        "finalizada",
    }:
        loan.status = _loan_active_status()

    _save_with_user(loan, user)


# ============================================================
# VISTA PRINCIPAL

@login_required
@require_GET
def loan_payment_manager(request):
    return render(
        request,
        "prestamos/manager/loan_payment_manager.html",
    )


# ============================================================
# DATATABLE

@login_required
@require_GET
def payment_manager_datatable(request):
    try:
        draw = int(request.GET.get("draw", 1) or 1)
        start = max(int(request.GET.get("start", 0) or 0), 0)
        length = int(request.GET.get("length", 10) or 10)
        length = 10 if length <= 0 else min(length, 100)

        search = str(request.GET.get("search[value]", "") or "").strip()
        filter_name = str(request.GET.get("filter", "pending") or "pending").strip()

        pending = _payment_pending()
        approved = _payment_approved()
        rejected = _payment_rejected()
        reversed_status = _payment_reversed()
        pending_reversal = _payment_pending_reversal()

        queryset = (
            LoanPayment.objects
            .filter(is_active=True)
            .select_related(
                "loan",
                "loan__person",
                "installment",
                "payment_type",
                "status",
            )
        )

        if filter_name == "pending":
            queryset = queryset.filter(status__in=[pending, pending_reversal])
        elif filter_name == "approved":
            queryset = queryset.filter(status=approved)
        elif filter_name == "rejected":
            queryset = queryset.filter(status=rejected)
        elif filter_name == "reversed":
            queryset = queryset.filter(status=reversed_status)
        else:
            queryset = queryset.filter(
                status__in=[
                    pending,
                    approved,
                    rejected,
                    reversed_status,
                    pending_reversal,
                ]
            )

        records_total = LoanPayment.objects.filter(is_active=True).count()

        if search:
            employee_person_ids = list(
                Employee.objects
                .filter(code__icontains=search)
                .values_list("person_id", flat=True)
            )

            search_q = (
                Q(loan__person__first_name__icontains=search)
                | Q(loan__person__second_name__icontains=search)
                | Q(loan__person__last_name_1__icontains=search)
                | Q(loan__person__last_name_2__icontains=search)
                | Q(loan__person__dv__icontains=search)
                | Q(payment_type__name__icontains=search)
                | Q(status__name__icontains=search)
            )

            if search.isdigit():
                search_q |= (
                    Q(id=int(search))
                    | Q(loan_id=int(search))
                    | Q(loan__person__rut=int(search))
                )

            if employee_person_ids:
                search_q |= Q(loan__person_id__in=employee_person_ids)

            queryset = queryset.filter(search_q)

        order_column = int(request.GET.get("order[0][column]", 7) or 7)
        order_direction = str(request.GET.get("order[0][dir]", "desc") or "desc").lower()

        order_fields = {
            0: "loan_id",
            1: "loan__person_id",
            2: "loan__person__rut",
            3: "loan__person__first_name",
            4: "payment_type__name",
            5: "installment__installment_number",
            6: "amount",
            7: "created_at",
            8: "status__name",
            9: "id",
        }

        order_field = order_fields.get(order_column, "created_at")

        if order_direction == "desc":
            order_field = f"-{order_field}"

        queryset = queryset.order_by(order_field, "-id")

        records_filtered = queryset.count()
        page = list(queryset[start:start + length])

        person_ids = {payment.loan.person_id for payment in page}

        employee_codes = {
            row["person_id"]: row["code"]
            for row in (
                Employee.objects
                .filter(person_id__in=person_ids)
                .values("person_id", "code")
            )
        }

        loan_ids = {payment.loan_id for payment in page}

        latest_reversible = {
            row["loan_id"]: row["latest_id"]
            for row in (
                LoanPayment.objects
                .filter(
                    loan_id__in=loan_ids,
                    status__in=[approved, pending_reversal],
                    is_active=True,
                )
                .values("loan_id")
                .annotate(latest_id=Max("id"))
            )
        }

        data = []

        for payment in page:
            person = payment.loan.person
            status_name = payment.status.name if payment.status else ""

            normalized_status = _normalize(status_name)

            status_class = "secondary"

            if normalized_status == "pendiente":
                status_class = "warning"

            elif "pendiente" in normalized_status and "reversa" in normalized_status:
                status_class = "warning"

            elif "aprobad" in normalized_status or "pagad" in normalized_status:
                status_class = "success"

            elif "rechaz" in normalized_status:
                status_class = "danger"

            elif "revers" in normalized_status:
                status_class = "secondary"

            data.append({
                "id": payment.id,
                "loan_id": payment.loan_id,
                "employee_code": employee_codes.get(person.id, ""),
                "rut": _person_rut(person),
                "person_name": _person_full_name(person),
                "payment_type": payment.payment_type.name if payment.payment_type else "",
                "installment": (
                    payment.installment.installment_number
                    if payment.installment
                    else None
                ),
                "amount": str(payment.amount or 0),
                "date": _format_datetime(payment.created_at),
                "status": status_name,
                "status_class": status_class,
                "can_approve": payment.status_id == pending.id,
                "can_reject": payment.status_id == pending.id,
                "can_request_reversal": (
                    payment.status_id == approved.id
                    and latest_reversible.get(payment.loan_id) == payment.id
                ),
                "can_approve_reversal": (
                    payment.status_id == pending_reversal.id
                    and latest_reversible.get(payment.loan_id) == payment.id
                ),
                "can_reject_reversal": payment.status_id == pending_reversal.id,
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        })

    except Exception as error:
        return JsonResponse({
            "draw": int(request.GET.get("draw", 1) or 1),
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
            "error": str(error),
        }, status=500)


# ============================================================
# APROBAR / RECHAZAR PAGO

@login_required
@require_POST
def payment_action(request, payment_id):
    saved_paths = []

    try:
        action = str(request.POST.get("action", "") or "").strip().lower()

        if action not in {"approve", "reject"}:
            raise ValueError("La acción seleccionada no es válida.")

        with transaction.atomic():
            payment = (
                LoanPayment.objects
                .select_for_update(of=("self",))
                .select_related(
                    "loan",
                    "loan__rate",
                    "loan__collection_method",
                    "loan__status",
                    "payment_type",
                    "status",
                )
                .filter(pk=payment_id, is_active=True)
                .first()
            )

            if not payment:
                raise ValueError("No se encontró el pago.")

            pending = _payment_pending()

            if payment.status_id != pending.id:
                raise ValueError("Solo se pueden gestionar pagos pendientes.")

            loan = (
                Loan.objects
                .select_for_update()
                .select_related("rate", "collection_method", "status")
                .get(pk=payment.loan_id)
            )
            payment.loan = loan

            kind = _payment_kind(payment)

            if action == "reject":
                reason = str(request.POST.get("reason", "") or "").strip()

                if not reason:
                    raise ValueError("Debe indicar el motivo del rechazo.")

                if kind["insolvent"]:
                    pending_installment = _installment_pending()
                    pending_amortization = _installment_pending_amortization()

                    for installment in (
                        LoanInstallment.objects
                        .select_for_update()
                        .filter(
                            loan=loan,
                            status=pending_amortization,
                            is_active=True,
                        )
                    ):
                        installment.status = pending_installment
                        installment.collection_method = loan.collection_method
                        _save_with_user(installment, request.user)

                if kind["external"] and payment.installment_id:
                    installment = (
                        LoanInstallment.objects
                        .select_for_update()
                        .get(pk=payment.installment_id)
                    )
                    installment.status = _installment_pending()
                    _save_with_user(installment, request.user)

                payment.status = _payment_rejected()
                payment.status_changed_at = timezone.now()
                _save_with_user(payment, request.user)

                return JsonResponse({
                    "status": "ok",
                    "message": "Solicitud de pago rechazada correctamente.",
                })

            uploaded_file = request.FILES.get("document")
            resolution = str(request.POST.get("resolution", "") or "").strip()

            is_partial_with_recalculation = (
                (kind["prepayment"] or kind["amortization"])
                and Decimal(payment.amount or 0) > 0
                and Decimal(payment.amount or 0) < Decimal(loan.principal_balance or 0)
            )

            months_from_current = _recalc_months_from_request(
                request,
                required=is_partial_with_recalculation,
            )

            approval_document = None

            if kind["amortization"] or kind["insolvent"]:
                if not uploaded_file:
                    raise ValueError("En amortización el documento PDF es obligatorio.")

                if not resolution:
                    raise ValueError("En amortización el número de resolución es obligatorio.")

                if not resolution.isdigit():
                    raise ValueError("El número de resolución debe contener solamente números.")

            if uploaded_file:
                approval_document, stored_path = _save_document(
                    request,
                    uploaded_file,
                    payment,
                    "approval",
                    "Aprobación de Pago de Préstamo",
                )
                saved_paths.append(stored_path)

                _create_with_user(
                    LoanPaymentDocument,
                    request.user,
                    payment=payment,
                    document=approval_document,
                )

            if resolution:
                if not approval_document:
                    raise ValueError(
                        "Para guardar el número de resolución debe adjuntar el documento PDF."
                    )

                number_type = _document_number_type(
                    "Número de Resolución",
                    2,
                    request.user,
                )
                number = int(resolution)

                duplicate = (
                    LoanDocumentNumber.objects
                    .filter(
                        number_type=number_type,
                        number=number,
                        is_active=True,
                    )
                    .exclude(
                        document__loan_payment_documents__payment=payment,
                    )
                    .exists()
                )

                if duplicate:
                    raise ValueError("El número de resolución ya fue utilizado.")

                _create_with_user(
                    LoanDocumentNumber,
                    request.user,
                    document=approval_document,
                    number_type=number_type,
                    number=number,
                )

            payment.status = _payment_approved()
            payment.status_changed_at = timezone.now()
            _save_with_user(payment, request.user)

            if kind["external"]:
                if not payment.installment_id:
                    raise ValueError("El pago extrasistema no posee dividendo asociado.")

                installment = (
                    LoanInstallment.objects
                    .select_for_update()
                    .get(pk=payment.installment_id, loan=loan)
                )

                if installment.status_id not in {
                    _installment_pending().id,
                    _installment_pending_payment().id,
                }:
                    raise ValueError("El dividendo no está disponible para ser procesado.")

                principal = Decimal(installment.principal or 0)
                interest = Decimal(installment.interest or 0)

                installment.status = _installment_paid()
                _save_with_user(installment, request.user)

                loan.principal_balance = max(
                    Decimal("0"),
                    Decimal(loan.principal_balance or 0) - principal,
                )
                loan.interest_balance = max(
                    Decimal("0"),
                    Decimal(loan.interest_balance or 0) - interest,
                )
                loan.principal_paid = Decimal(loan.principal_paid or 0) + principal
                loan.interest_paid = Decimal(loan.interest_paid or 0) + interest

                _sync_installments_paid(loan, request.user)
                _deduct_external_contributions(payment, request.user)
                _update_loan_paid_status(loan, request.user)

                return JsonResponse({
                    "status": "ok",
                    "message": "Solicitud de pago extrasistema aprobada correctamente.",
                })

            if kind["insolvent"]:
                first_day = timezone.localdate().replace(day=1)
                amortization_status = _installment_pending_amortization()

                installments = list(
                    LoanInstallment.objects
                    .select_for_update()
                    .filter(
                        loan=loan,
                        status=amortization_status,
                        due_date__lt=first_day,
                        is_active=True,
                    )
                    .order_by("installment_number")
                )

                if not installments:
                    raise ValueError(
                        "No existen dividendos en estado por amortizar para este préstamo."
                    )

                total = sum((Decimal(item.amount or 0) for item in installments), Decimal("0"))

                if total.quantize(MONEY) != Decimal(payment.amount or 0).quantize(MONEY):
                    raise ValueError(
                        "El total de dividendos por amortizar no coincide con el monto del pago."
                    )

                principal = sum((Decimal(item.principal or 0) for item in installments), Decimal("0"))
                interest = sum((Decimal(item.interest or 0) for item in installments), Decimal("0"))
                amortized_method = _amortized_collection_method()

                for installment in installments:
                    installment.status = _installment_paid()

                    if amortized_method:
                        installment.collection_method = amortized_method

                    _save_with_user(installment, request.user)

                loan.principal_balance = max(
                    Decimal("0"),
                    Decimal(loan.principal_balance or 0) - principal,
                )
                loan.interest_balance = max(
                    Decimal("0"),
                    Decimal(loan.interest_balance or 0) - interest,
                )
                loan.principal_paid = Decimal(loan.principal_paid or 0) + principal
                loan.interest_paid = Decimal(loan.interest_paid or 0) + interest

                _save_with_user(loan, request.user)
                _deduct_amortization_contributions(payment, request.user)
                recalculated_count = _recalculate_installments(loan, 0, request.user)
                _sync_installments_paid(loan, request.user)
                _update_loan_paid_status(loan, request.user)

                return JsonResponse({
                    "status": "ok",
                    "message": (
                        "Amortización de insolutos aprobada correctamente. "
                        f"Dividendos recalculados: {recalculated_count}."
                    ),
                })

            if kind["prepayment"] or kind["insurance"] or kind["amortization"]:
                amount = Decimal(payment.amount or 0)

                loan.principal_balance = max(
                    Decimal("0"),
                    Decimal(loan.principal_balance or 0) - amount,
                )
                loan.principal_paid = Decimal(loan.principal_paid or 0) + amount
                _save_with_user(loan, request.user)

                if kind["amortization"]:
                    _deduct_amortization_contributions(payment, request.user)

                if kind["insurance"]:
                    months_from_current = 0

                loan.refresh_from_db(fields=["principal_balance", "principal_paid", "interest_balance", "interest_paid"])

                recalculated_count = _recalculate_installments(
                    loan,
                    months_from_current,
                    request.user,
                )
                _update_loan_paid_status(loan, request.user)

                return JsonResponse({
                    "status": "ok",
                    "message": (
                        "Solicitud de pago aprobada correctamente. "
                        f"Dividendos recalculados: {recalculated_count}."
                    ),
                })

            raise ValueError(
                f"Tipo de pago no soportado para aprobación: "
                f"{payment.payment_type.name if payment.payment_type else '-'}."
            )

    except ValueError as error:
        for path in saved_paths:
            if default_storage.exists(path):
                default_storage.delete(path)

        return JsonResponse(
            {"status": "error", "message": str(error)},
            status=400,
        )

    except Exception as error:
        for path in saved_paths:
            if default_storage.exists(path):
                default_storage.delete(path)

        return JsonResponse(
            {"status": "error", "message": f"Error al gestionar el pago: {error}"},
            status=500,
        )


# ============================================================
# INFORMACIÓN PARA SOLICITAR REVERSA

@login_required
@require_GET
def payment_reversal_info(request, payment_id):
    try:
        payment = get_object_or_404(
            LoanPayment.objects.select_related(
                "loan",
                "loan__person",
                "payment_type",
                "status",
            ),
            pk=payment_id,
            is_active=True,
        )

        approved = _payment_approved()

        if payment.status_id != approved.id:
            raise ValueError("Solo se puede solicitar reversa de pagos aprobados.")

        latest_id = _latest_reversible_payment_id(payment.loan_id)

        if latest_id != payment.id:
            raise ValueError(
                "Solo se puede solicitar la reversa del último pago del préstamo."
            )

        partner = _partner_for_loan(payment.loan)

        if not partner:
            raise ValueError("No se encontró el socio asociado al préstamo.")

        deposit_amount = _deposit_origin_amount(payment)

        contributions = []

        if deposit_amount > 0:
            contributions = [
                {
                    "id": row.contribution_type_id,
                    "description": row.contribution_type.description,
                    "balance": str(row.amount or 0),
                }
                for row in (
                    PartnerContribution.objects
                    .filter(partner=partner, is_active=True)
                    .select_related("contribution_type")
                    .order_by("contribution_type__description")
                )
            ]

            if not contributions:
                raise ValueError(
                    "El pago contiene depósito, pero el socio no posee aportes disponibles para recibirlo."
                )

        return JsonResponse({
            "status": "ok",
            "payment_id": payment.id,
            "loan_id": payment.loan_id,
            "payment_type": payment.payment_type.name if payment.payment_type else "",
            "payment_amount": str(payment.amount or 0),
            "has_deposit": deposit_amount > 0,
            "deposit_amount": str(deposit_amount),
            "contributions": contributions,
        })

    except ValueError as error:
        return JsonResponse(
            {"status": "error", "message": str(error)},
            status=400,
        )


# ============================================================
# SOLICITAR REVERSA

@login_required
@require_POST
def payment_reversal_request(request, payment_id):
    saved_path = None

    try:
        reason = str(request.POST.get("reason", "") or "").strip()

        if not reason:
            raise ValueError("Debe ingresar un motivo para solicitar la reversa.")

        uploaded_file = request.FILES.get("document")
        _validate_pdf(uploaded_file)

        with transaction.atomic():
            payment = (
                LoanPayment.objects
                .select_for_update()
                .select_related(
                    "loan",
                    "loan__person",
                    "payment_type",
                    "status",
                )
                .filter(pk=payment_id, is_active=True)
                .first()
            )

            if not payment:
                raise ValueError("No se encontró el pago.")

            approved = _payment_approved()

            if payment.status_id != approved.id:
                raise ValueError("Solo se puede solicitar reversa de pagos aprobados.")

            latest_id = _latest_reversible_payment_id(payment.loan_id)

            if latest_id != payment.id:
                raise ValueError(
                    "Solo se puede solicitar la reversa del último pago del préstamo."
                )

            deposit_amount = _deposit_origin_amount(payment)
            contribution_type = None

            if deposit_amount > 0:
                try:
                    contribution_type_id = int(
                        request.POST.get("deposit_contribution_type", 0) or 0
                    )
                except (TypeError, ValueError):
                    contribution_type_id = 0

                if contribution_type_id <= 0:
                    raise ValueError(
                        "Debe seleccionar el aporte que recibirá el dinero proveniente del depósito."
                    )

                partner = _partner_for_loan(payment.loan)

                relation = (
                    PartnerContribution.objects
                    .filter(
                        partner=partner,
                        contribution_type_id=contribution_type_id,
                        is_active=True,
                    )
                    .select_related("contribution_type")
                    .first()
                )

                if not relation:
                    raise ValueError("El aporte seleccionado no pertenece al socio.")

                contribution_type = relation.contribution_type

            document, saved_path = _save_document(
                request,
                uploaded_file,
                payment,
                "reversal",
                "Solicitud de Reversa de Pago",
            )

            reversal = _create_with_user(
                LoanPaymentReversal,
                request.user,
                payment=payment,
                reason=reason,
                document=document,
                ip=_get_client_ip(request),
                deposit_contribution_type=contribution_type,
            )

            payment.status = _payment_pending_reversal()
            payment.status_changed_at = timezone.now()
            _save_with_user(payment, request.user)

        return JsonResponse({
            "status": "ok",
            "message": "Solicitud de reversa creada correctamente.",
            "reversal_id": reversal.id,
        })

    except ValueError as error:
        if saved_path and default_storage.exists(saved_path):
            default_storage.delete(saved_path)

        return JsonResponse(
            {"status": "error", "message": str(error)},
            status=400,
        )

    except Exception as error:
        if saved_path and default_storage.exists(saved_path):
            default_storage.delete(saved_path)

        return JsonResponse(
            {"status": "error", "message": f"Error al solicitar la reversa: {error}"},
            status=500,
        )


# ============================================================
# DECIDIR REVERSA
def _insolvent_installments_for_reversal(payment):
    amortized_method = _amortized_collection_method()
    paid = _installment_paid()

    queryset = (
        LoanInstallment.objects
        .select_for_update()
        .filter(
            loan=payment.loan,
            status=paid,
            is_active=True,
        )
        .order_by("-installment_number")
    )

    if amortized_method:
        queryset = queryset.filter(collection_method=amortized_method)

    selected = []
    total = Decimal("0")
    target = Decimal(payment.amount or 0).quantize(MONEY)

    for installment in queryset:
        if total >= target:
            break

        selected.append(installment)
        total += Decimal(installment.amount or 0)

    if total.quantize(MONEY) != target:
        raise ValueError(
            "No fue posible identificar con seguridad los dividendos amortizados de este pago."
        )

    return list(reversed(selected))


@login_required
@require_POST
def payment_reversal_decision(request, payment_id):
    try:
        action = str(request.POST.get("action", "") or "").strip().lower()
        reason = str(request.POST.get("reason", "") or "").strip()

        if action not in {"approve", "reject"}:
            raise ValueError("La acción de reversa no es válida.")

        if action == "reject" and not reason:
            raise ValueError("Debe ingresar el motivo del rechazo.")

        with transaction.atomic():
            payment = (
                LoanPayment.objects
                .select_for_update(of=("self",))
                .select_related(
                    "loan",
                    "loan__rate",
                    "loan__collection_method",
                    "loan__status",
                    "payment_type",
                    "status",
                )
                .filter(pk=payment_id, is_active=True)
                .first()
            )

            if not payment:
                raise ValueError("No se encontró el pago.")

            if payment.status_id != _payment_pending_reversal().id:
                raise ValueError("El pago no se encuentra pendiente de reversa.")

            reversal = (
                LoanPaymentReversal.objects
                .select_for_update(of=("self",))
                .select_related("document")
                .filter(payment=payment, is_active=True)
                .order_by("-id")
                .first()
            )

            if not reversal:
                raise ValueError("No existe una solicitud de reversa para este pago.")

            if action == "reject":
                payment.status = _payment_approved()
                payment.status_changed_at = timezone.now()
                _save_with_user(payment, request.user)

                return JsonResponse({
                    "status": "ok",
                    "message": "Solicitud de reversa rechazada correctamente.",
                })

            if _latest_reversible_payment_id(payment.loan_id) != payment.id:
                raise ValueError(
                    "No se puede aprobar la reversa porque este ya no es el último pago del préstamo."
                )

            loan = (
                Loan.objects
                .select_for_update()
                .select_related("rate", "collection_method", "status")
                .get(pk=payment.loan_id)
            )
            payment.loan = loan

            kind = _payment_kind(payment)

            if kind["external"]:
                if not payment.installment_id:
                    raise ValueError("El pago extrasistema no posee dividendo asociado.")

                installment = (
                    LoanInstallment.objects
                    .select_for_update()
                    .get(pk=payment.installment_id, loan=loan)
                )

                principal = Decimal(installment.principal or 0)
                interest = Decimal(installment.interest or 0)

                installment.status = _installment_pending()
                _save_with_user(installment, request.user)

                loan.principal_balance = Decimal(payment.previous_balance or 0)
                loan.interest_balance = Decimal(loan.interest_balance or 0) + interest
                loan.principal_paid = max(
                    Decimal("0"),
                    Decimal(loan.principal_paid or 0) - principal,
                )
                loan.interest_paid = max(
                    Decimal("0"),
                    Decimal(loan.interest_paid or 0) - interest,
                )

                _sync_installments_paid(loan, request.user)
                _restore_external_contributions(payment, request.user)
                _update_loan_paid_status(loan, request.user)

            elif kind["insolvent"]:
                installments = _insolvent_installments_for_reversal(payment)

                principal = sum(
                    (Decimal(item.principal or 0) for item in installments),
                    Decimal("0"),
                )
                interest = sum(
                    (Decimal(item.interest or 0) for item in installments),
                    Decimal("0"),
                )

                for installment in installments:
                    installment.status = _installment_pending()
                    installment.collection_method = loan.collection_method
                    _save_with_user(installment, request.user)

                loan.principal_balance = Decimal(payment.previous_balance or 0)
                loan.interest_balance = Decimal(loan.interest_balance or 0) + interest
                loan.principal_paid = max(
                    Decimal("0"),
                    Decimal(loan.principal_paid or 0) - principal,
                )
                loan.interest_paid = max(
                    Decimal("0"),
                    Decimal(loan.interest_paid or 0) - interest,
                )

                _save_with_user(loan, request.user)
                _restore_amortization_contributions(payment, request.user)
                _recalculate_installments(loan, 1, request.user)
                _sync_installments_paid(loan, request.user)
                _update_loan_paid_status(loan, request.user)

            elif kind["prepayment"] or kind["insurance"] or kind["amortization"]:
                loan.principal_balance = Decimal(payment.previous_balance or 0)
                loan.principal_paid = max(
                    Decimal("0"),
                    Decimal(loan.principal_paid or 0) - Decimal(payment.amount or 0),
                )

                _save_with_user(loan, request.user)

                if kind["amortization"]:
                    _restore_amortization_contributions(payment, request.user)

                _recalculate_installments(loan, 1, request.user)
                _update_loan_paid_status(loan, request.user)

            else:
                raise ValueError(
                    f"Tipo de pago no soportado para reversa: "
                    f"{payment.payment_type.name if payment.payment_type else '-'}."
                )

            _send_reversal_deposit_to_contribution(
                payment,
                reversal,
                request.user,
            )

            payment.status = _payment_reversed()
            payment.status_changed_at = timezone.now()
            _save_with_user(payment, request.user)

        return JsonResponse({
            "status": "ok",
            "message": "Reversa aprobada correctamente.",
        })

    except ValueError as error:
        return JsonResponse(
            {"status": "error", "message": str(error)},
            status=400,
        )

    except Exception as error:
        return JsonResponse(
            {"status": "error", "message": f"Error al gestionar la reversa: {error}"},
            status=500,
        )
