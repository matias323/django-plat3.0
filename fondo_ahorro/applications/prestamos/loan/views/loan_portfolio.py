from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models.document import DocumentType
from core.models.employee import Employee
from core.models.partner import Partner, PartnerContribution

from ..models.loan import (
    Loan,
    LoanCollectionMethod,
    LoanCollectionMethodRecord,
    LoanDocument,
    LoanGuarantor,
    LoanInstallment,
    LoanRate,
    LoanRateRecord,
)
from ..models.payment import LoanPayment


# ============================================================
# FUNCIONES GENERALES
def _person_full_name(person):
    if not person:
        return ""

    values = [person.first_name, person.second_name, person.last_name_1, person.last_name_2]
    return " ".join(str(value).strip() for value in values if value)


def _person_rut(person):
    return f"{person.rut}-{person.dv}" if person else ""


def _employee_codes(person_ids):
    if not person_ids:
        return {}

    return {
        employee["person_id"]: employee["code"]
        for employee in Employee.objects.filter(person_id__in=person_ids).values("person_id", "code")
    }


def _person_ids_by_employee_code(search):
    if not search:
        return []

    return list(Employee.objects.filter(code__icontains=search).values_list("person_id", flat=True))


def _format_date(value):
    return value.strftime("%d-%m-%Y") if value else ""


def _document_url(document):
    if not document or not document.route:
        return ""

    try:
        return default_storage.url(document.route)
    except Exception:
        return document.route


def _status_contains(status, *tokens):
    value = str(status.name if status else "").strip().lower()
    return any(token.lower() in value for token in tokens)


def _dipreca_code_value(dipreca):
    if not dipreca:
        return ""

    for field_name in ["code", "dipreca_code", "codigo", "codigo_dipreca"]:
        if hasattr(dipreca, field_name):
            value = getattr(dipreca, field_name)

            if value is not None:
                return str(value)

    return ""


# ============================================================
# CARTERA DE PRESTAMOS
@login_required
def loan_portfolio(request):
    return render(request, "prestamos/portfolio/loan_portfolio.html")


# ============================================================
# DATATABLE CARTERA DE PRESTAMOS
@login_required
@require_GET
def loan_portfolio_datatable(request):
    try:
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
        search = (request.GET.get("search[value]", "") or "").strip()
        order_column = int(request.GET.get("order[0][column]", 0))
        order_direction = str(request.GET.get("order[0][dir]", "desc")).lower()

        queryset = (
            Loan.objects
            .filter(is_active=True)
            .select_related(
                "person", "loan_type", "type_concept", "type_concept__concept",
                "collection_method", "rate", "status",
            )
        )

        records_total = queryset.count()

        if search:
            search_filter = (
                Q(unique_code__icontains=search)
                | Q(person__first_name__icontains=search)
                | Q(person__second_name__icontains=search)
                | Q(person__last_name_1__icontains=search)
                | Q(person__last_name_2__icontains=search)
                | Q(person__dv__icontains=search)
                | Q(loan_type__name__icontains=search)
                | Q(type_concept__concept__name__icontains=search)
                | Q(collection_method__name__icontains=search)
                | Q(status__name__icontains=search)
            )

            if search.isdigit():
                search_filter |= Q(id=int(search)) | Q(person__rut=int(search))

            employee_person_ids = _person_ids_by_employee_code(search)
            if employee_person_ids:
                search_filter |= Q(person_id__in=employee_person_ids)

            queryset = queryset.filter(search_filter)

        records_filtered = queryset.count()

        order_fields = {
            0: "id", 1: "unique_code", 2: "person__first_name", 3: "loan_type__name",
            4: "type_concept__concept__name", 5: "principal_balance", 6: "start_date",
            7: "collection_method__name", 8: "term", 9: "status__name",
        }

        order_field = order_fields.get(order_column, "id")
        if order_direction == "desc":
            order_field = f"-{order_field}"

        loans = list(queryset.order_by(order_field, "-id")[start:start + length])
        employee_codes = _employee_codes([loan.person_id for loan in loans if loan.person_id])

        data = []

        for loan in loans:
            data.append({
                "id": loan.id,
                "unique_code": loan.unique_code or "",
                "employee_code": employee_codes.get(loan.person_id, ""),
                "rut": _person_rut(loan.person),
                "person_name": _person_full_name(loan.person),
                "loan_type": loan.loan_type.name if loan.loan_type else "",
                "concept": (
                    loan.type_concept.concept.name
                    if loan.type_concept and loan.type_concept.concept else ""
                ),
                "principal_balance": loan.principal_balance or 0,
                "start_date": _format_date(loan.start_date),
                "collection_method": loan.collection_method.name if loan.collection_method else "",
                "remaining_term": max(int(loan.term or 0) - int(loan.installments_paid or 0), 0),
                "status": loan.status.name if loan.status else "",
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        })

    except Exception as error:
        return JsonResponse({
            "draw": int(request.GET.get("draw", 1)),
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
            "error": str(error),
        }, status=500)


def _user_display_name(user):
    if not user:
        return "-"

    person = getattr(user, "person", None)

    if person:
        name = " ".join(
            value.strip()
            for value in [
                getattr(person, "first_name", "") or "",
                getattr(person, "last_name_1", "") or "",
            ]
            if value and value.strip()
        )

        if name:
            return name

    first_name = str(getattr(user, "first_name", "") or "").strip()
    last_name = str(getattr(user, "last_name", "") or "").strip()

    name = " ".join(value for value in [first_name, last_name] if value)

    return name or str(getattr(user, "username", "") or "-")


# ============================================================
# DETALLE DE PRESTAMO
@login_required
@require_GET
def loan_detail(request, loan_id):
    loan = get_object_or_404(
        Loan.objects.select_related(
            "request", "person", "loan_type", "type_concept", "type_concept__concept",
            "collection_method", "rate", "status", "previous_loan",
        ),
        pk=loan_id,
        is_active=True,
    )

    employee = (
        Employee.objects
        .select_related("grade")
        .filter(person_id=loan.person_id, is_active=True)
        .order_by("id")
        .first()
    )

    installments = list(
        LoanInstallment.objects
        .filter(loan=loan, is_active=True)
        .select_related("collection_method", "status")
        .order_by("installment_number")
    )

    payment_pending_installments = set(
        LoanPayment.objects
        .filter(
            loan=loan,
            installment__isnull=False,
            is_active=True,
            status__name__icontains="Pend",
        )
        .values_list("installment_id", flat=True)
    )

    installment_rows = []

    for installment in installments:
        previous = next(
            (item for item in reversed(installments) if item.installment_number < installment.installment_number),
            None,
        )

        previous_ok = previous is None or _status_contains(previous.status, "pagad", "paid")
        collection_name = str(installment.collection_method.name if installment.collection_method else "").lower()

        installment_rows.append({
            "installment": installment,
            "can_pay": (
                _status_contains(installment.status, "pendiente", "pending")
                and ("extra" in collection_name and "sistema" in collection_name)
                and previous_ok
                and installment.id not in payment_pending_installments
            ),
        })

    first_day_current_month = timezone.localdate().replace(day=1)

    overdue_installments = [
        item for item in installments
        if item.due_date < first_day_current_month
        and _status_contains(item.status, "pendiente", "pending")
    ]

    overdue_count = len(overdue_installments)
    overdue_principal = sum((Decimal(item.principal or 0) for item in overdue_installments), Decimal("0"))
    overdue_interest = sum((Decimal(item.interest or 0) for item in overdue_installments), Decimal("0"))
    overdue_total = sum((Decimal(item.amount or 0) for item in overdue_installments), Decimal("0"))

    payments = (
        LoanPayment.objects
        .filter(loan=loan, is_active=True)
        .select_related("installment", "payment_type", "status", "user_create")
        .order_by("-created_at")
    )

    partner = Partner.objects.filter(person_id=loan.person_id, is_active=True).first()

    contributions = (
        PartnerContribution.objects
        .filter(partner=partner, is_active=True)
        .select_related("contribution_type")
        .order_by("contribution_type__description")
        if partner else PartnerContribution.objects.none()
    )

    total_contributions = contributions.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    minimum_prepayment = (Decimal(loan.principal_balance or 0) * Decimal("0.05")).quantize(Decimal("0.01"))

    collection_records = (
        LoanCollectionMethodRecord.objects
        .filter(loan=loan, is_active=True)
        .select_related("collection_method", "dipreca_code", "document", "user_create")
        .order_by("-created_at")
    )

    dipreca_record = collection_records.filter(dipreca_code__isnull=False).first()
    dipreca_code = _dipreca_code_value(dipreca_record.dipreca_code) if dipreca_record else ""

    rate_records = (
        LoanRateRecord.objects
        .filter(loan=loan, is_active=True)
        .select_related("previous_rate", "new_rate", "document", "user_create")
        .order_by("-created_at")
    )

    guarantors = (
        LoanGuarantor.objects
        .filter(loan=loan, is_active=True)
        .select_related("person")
        .order_by("id")
    )

    guarantor_rows = []

    for guarantor in guarantors:
        child_loan = (
            Loan.objects
            .filter(previous_loan=loan, person=guarantor.person, is_active=True)
            .exclude(status__name__icontains="Recuper")
            .order_by("-id")
            .first()
        )

        guarantor_rows.append({
            "relation": guarantor,
            "rut": _person_rut(guarantor.person),
            "name": _person_full_name(guarantor.person),
            "child_loan": child_loan,
        })

    loan_documents = (
        LoanDocument.objects
        .filter(loan=loan, is_active=True)
        .select_related("document", "document_type")
        .order_by("-created_at")
    )

    document_rows = [{"relation": relation, "url": _document_url(relation.document)} for relation in loan_documents]
    rate_rows = [{"record": record, "url": _document_url(record.document)} for record in rate_records]
    collection_rows = [
        {
            "record": record,
            "url": _document_url(record.document),
            "dipreca_code": _dipreca_code_value(record.dipreca_code),
            "user_name": _user_display_name(record.user_create),
        }
        for record in collection_records
    ]

    return render(
        request,
        "prestamos/portfolio/loan_detail_modal.html",
        {
            "loan": loan,
            "employee": employee,
            "person_name": _person_full_name(loan.person),
            "person_rut": _person_rut(loan.person),
            "installment_rows": installment_rows,
            "installments": installments,
            "overdue_installments": overdue_installments,
            "overdue_count": overdue_count,
            "overdue_principal": overdue_principal,
            "overdue_interest": overdue_interest,
            "overdue_total": overdue_total,
            "payments": payments,
            "partner": partner,
            "contributions": contributions,
            "total_contributions": total_contributions,
            "minimum_prepayment": minimum_prepayment,
            "collection_records": collection_records,
            "collection_rows": collection_rows,
            "dipreca_code": dipreca_code,
            "rate_records": rate_records,
            "rate_rows": rate_rows,
            "guarantor_rows": guarantor_rows,
            "document_rows": document_rows,
        },
    )
