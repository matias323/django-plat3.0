from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import unicodedata

from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Prefetch
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.models.employee import Employee

from ..models.loan import (
    Loan,
    LoanCollectionMethod,
    LoanConcept,
    LoanInstallment,
    LoanInstallmentStatus,
    LoanRate,
    LoanStatus,
    LoanType,
)


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def _normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.strip().lower().split())


def _reference(model, aliases, fallback_id=None):
    aliases = {_normalize(alias) for alias in aliases if alias}

    for item in model.objects.filter(is_active=True).order_by("id"):
        if _normalize(getattr(item, "name", "")) in aliases:
            return item

    if fallback_id:
        return model.objects.filter(pk=fallback_id, is_active=True).first()

    return None


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
        row["person_id"]: row["code"]
        for row in Employee.objects.filter(person_id__in=person_ids).values("person_id", "code")
    }


def _date_param(request, name, required=False):
    value = str(request.GET.get(name, "") or "").strip()

    if not value:
        if required:
            raise ValueError(f"Debe seleccionar la fecha {name.replace('_', ' ')}.")
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"La fecha {name.replace('_', ' ')} no es válida.") from exc


def _int_param(request, name):
    try:
        return max(int(request.GET.get(name, 0) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _local_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()

    return value


def _first_installment_amount(loan):
    installments = getattr(loan, "report_installments", [])
    return Decimal(installments[0].amount or 0) if installments else Decimal("0")


def _status_pending():
    return _reference(LoanInstallmentStatus, ["Pendiente", "Pending"], 1)


def _status_paid():
    return _reference(LoanInstallmentStatus, ["Pagado", "Pagada", "Paid"], 2)


def _recovered_loan_status():
    return _reference(
        LoanStatus,
        ["Recuperado", "Recuperada", "Recovered", "Recuperado de avales", "Recuperada de avales"],
        5,
    )


def _excel_response(workbook, filename):
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)

    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _prepare_sheet(sheet, title, subtitle, headers):
    last_col = get_column_letter(len(headers))
    thin = Side(style="thin", color="D9D9D9")

    sheet.merge_cells(f"A1:{last_col}1")
    sheet["A1"] = title
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A1"].alignment = Alignment(horizontal="center")

    sheet.merge_cells(f"A2:{last_col}2")
    sheet["A2"] = subtitle
    sheet["A2"].alignment = Alignment(horizontal="center")

    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=4, column=column, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0D6EFD")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    sheet.freeze_panes = "A5"
    sheet.auto_filter.ref = f"A4:{last_col}4"


def _finish_sheet(sheet, currency_columns=None, date_columns=None):
    currency_columns = set(currency_columns or [])
    date_columns = set(date_columns or [])

    for row in range(5, sheet.max_row + 1):
        for column in currency_columns:
            sheet.cell(row=row, column=column).number_format = '$#,##0'

        for column in date_columns:
            sheet.cell(row=row, column=column).number_format = "dd-mm-yyyy"

    for column in range(1, sheet.max_column + 1):
        max_length = 0

        for row in range(1, sheet.max_row + 1):
            value = sheet.cell(row=row, column=column).value
            length = len(str(value)) if value is not None else 0
            max_length = max(max_length, length)

        sheet.column_dimensions[get_column_letter(column)].width = min(max(max_length + 2, 12), 40)


def _date_range_text(date_from, date_to):
    return (
        f"Desde: {date_from.strftime('%d-%m-%Y') if date_from else 'Todo'}"
        f" | Hasta: {date_to.strftime('%d-%m-%Y') if date_to else 'Todo'}"
    )


def _portfolio_queryset(request):
    date_from = _date_param(request, "fecha_desde")
    date_to = _date_param(request, "fecha_hasta")

    queryset = (
        Loan.objects
        .filter(is_active=True)
        .select_related(
            "person",
            "loan_type",
            "type_concept",
            "type_concept__concept",
            "collection_method",
            "rate",
            "status",
        )
        .prefetch_related(
            Prefetch(
                "installments",
                queryset=LoanInstallment.objects.filter(is_active=True).order_by("installment_number"),
                to_attr="report_installments",
            )
        )
        .annotate(
            total_balance=ExpressionWrapper(
                F("principal_balance") + F("interest_balance"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            )
        )
    )

    recovered = _recovered_loan_status()
    if recovered:
        queryset = queryset.exclude(status=recovered)

    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    loan_type_id = _int_param(request, "id_tipo_prestamo")
    concept_id = _int_param(request, "id_tipo_concepto")
    status_id = _int_param(request, "id_estado")
    collection_method_id = _int_param(request, "id_cobro_metodo")
    rate_id = _int_param(request, "id_tasa")
    mortgage = str(request.GET.get("hipotecario", "") or "").strip()

    if loan_type_id:
        queryset = queryset.filter(loan_type_id=loan_type_id)

    if concept_id:
        queryset = queryset.filter(type_concept__concept_id=concept_id)

    if status_id:
        queryset = queryset.filter(status_id=status_id)

    if collection_method_id:
        queryset = queryset.filter(collection_method_id=collection_method_id)

    if rate_id:
        queryset = queryset.filter(rate_id=rate_id)

    if mortgage in {"0", "1"}:
        queryset = queryset.filter(is_mortgage=(mortgage == "1"))

    order_map = {
        "created_at": "created_at",
        "start_date": "start_date",
        "end_date": "end_date",
        "loan_type": "loan_type__name",
        "concept": "type_concept__concept__name",
        "status": "status__name",
        "collection_method": "collection_method__name",
        "rate": "rate__rate",
        "name": "person__first_name",
        "unique_code": "unique_code",
        "loan_amount": "loan_amount",
        "interest_amount": "interest_amount",
        "principal_balance": "principal_balance",
        "interest_balance": "interest_balance",
        "total_balance": "total_balance",
        "mortgage": "is_mortgage",
    }

    order_key = str(request.GET.get("ordenar_por", "created_at") or "created_at")
    order_field = order_map.get(order_key, "created_at")
    direction = str(request.GET.get("direccion", "DESC") or "DESC").upper()

    if direction != "ASC":
        order_field = f"-{order_field}"

    return queryset.order_by(order_field, "-id"), date_from, date_to


# ============================================================
# VISTA PRINCIPAL
# ============================================================

@login_required
@require_GET
def loan_reports(request):
    context = {
        "loan_types": LoanType.objects.filter(is_active=True).order_by("name"),
        "concepts": LoanConcept.objects.filter(is_active=True).order_by("name"),
        "statuses": LoanStatus.objects.filter(is_active=True).order_by("name"),
        "collection_methods": LoanCollectionMethod.objects.filter(is_active=True).order_by("name"),
        "rates": LoanRate.objects.filter(is_active=True).order_by("rate", "name"),
    }

    return render(request, "prestamos/reports/loan_reports.html", context)


# ============================================================
# INFORME CARTERA DE PRÉSTAMOS
# ============================================================

@login_required
@require_GET
def report_portfolio_excel(request):
    queryset, date_from, date_to = _portfolio_queryset(request)
    loans = list(queryset)
    employee_codes = _employee_codes([loan.person_id for loan in loans if loan.person_id])

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cartera"

    headers = [
        "Código préstamo", "Código funcionario", "RUT", "Nombre", "Tipo", "Concepto", "Estado",
        "Método cobro", "Tasa", "Fecha creación", "Fecha entrada", "Fecha término", "Monto préstamo",
        "Interés préstamo", "Plazo", "Dividendo", "Plazo restante", "Saldo capital", "Saldo interés",
        "Saldo total", "Hipotecario",
    ]

    _prepare_sheet(sheet, "CARTERA DE PRÉSTAMOS", _date_range_text(date_from, date_to), headers)

    total_principal = Decimal("0")
    total_interest = Decimal("0")
    total_balance = Decimal("0")

    for row_number, loan in enumerate(loans, start=5):
        principal_balance = Decimal(loan.principal_balance or 0)
        interest_balance = Decimal(loan.interest_balance or 0)
        balance = principal_balance + interest_balance
        remaining_term = max(int(loan.term or 0) - int(loan.installments_paid or 0), 0)

        total_principal += principal_balance
        total_interest += interest_balance
        total_balance += balance

        values = [
            loan.unique_code or "",
            employee_codes.get(loan.person_id, ""),
            _person_rut(loan.person),
            _person_full_name(loan.person),
            loan.loan_type.name if loan.loan_type else "",
            loan.type_concept.concept.name if loan.type_concept and loan.type_concept.concept else "",
            loan.status.name if loan.status else "",
            loan.collection_method.name if loan.collection_method else "",
            f"{loan.rate.name} - {Decimal(loan.rate.rate or 0):.2f}%" if loan.rate else "",
            _local_date(loan.created_at),
            loan.start_date,
            loan.end_date,
            float(loan.loan_amount or 0),
            float(loan.interest_amount or 0),
            int(loan.term or 0),
            float(_first_installment_amount(loan)),
            remaining_term,
            float(principal_balance),
            float(interest_balance),
            float(balance),
            "Sí" if loan.is_mortgage else "No",
        ]

        for column, value in enumerate(values, start=1):
            sheet.cell(row=row_number, column=column, value=value)

    total_row = sheet.max_row + 1
    sheet.cell(row=total_row, column=17, value="Totales").font = Font(bold=True)
    sheet.cell(row=total_row, column=18, value=float(total_principal)).font = Font(bold=True)
    sheet.cell(row=total_row, column=19, value=float(total_interest)).font = Font(bold=True)
    sheet.cell(row=total_row, column=20, value=float(total_balance)).font = Font(bold=True)

    _finish_sheet(sheet, currency_columns=[13, 14, 16, 18, 19, 20], date_columns=[10, 11, 12])

    filename = f"Cartera_prestamos_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return _excel_response(workbook, filename)


# ============================================================
# INFORME INSOLUTOS
# ============================================================

@login_required
@require_GET
def report_unpaid_excel(request):
    date_from = _date_param(request, "fecha_desde")
    date_to = _date_param(request, "fecha_hasta")
    pending = _status_pending()

    queryset = LoanInstallment.objects.none()

    if pending:
        first_day_current_month = timezone.localdate().replace(day=1)

        queryset = (
            LoanInstallment.objects
            .filter(
                is_active=True,
                status=pending,
                due_date__lt=first_day_current_month,
                loan__is_active=True,
            )
            .select_related("loan", "loan__person")
        )

        if date_from:
            queryset = queryset.filter(due_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(due_date__lte=date_to)

        queryset = queryset.order_by("loan__person_id", "installment_number", "id")

    installments = list(queryset)
    employee_codes = _employee_codes([item.loan.person_id for item in installments if item.loan.person_id])

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Insolutos"

    headers = ["Código funcionario", "RUT", "Nombre", "Cuota", "Fecha dividendo", "Capital", "Interés", "Total"]
    _prepare_sheet(sheet, "INFORME DE INSOLUTOS", _date_range_text(date_from, date_to), headers)

    total_principal = Decimal("0")
    total_interest = Decimal("0")
    total_amount = Decimal("0")

    for row_number, installment in enumerate(installments, start=5):
        principal = Decimal(installment.principal or 0)
        interest = Decimal(installment.interest or 0)
        amount = principal + interest

        total_principal += principal
        total_interest += interest
        total_amount += amount

        values = [
            employee_codes.get(installment.loan.person_id, ""),
            _person_rut(installment.loan.person),
            _person_full_name(installment.loan.person),
            int(installment.installment_number or 0),
            installment.due_date,
            float(principal),
            float(interest),
            float(amount),
        ]

        for column, value in enumerate(values, start=1):
            sheet.cell(row=row_number, column=column, value=value)

    total_row = sheet.max_row + 1
    sheet.cell(row=total_row, column=5, value="Totales").font = Font(bold=True)
    sheet.cell(row=total_row, column=6, value=float(total_principal)).font = Font(bold=True)
    sheet.cell(row=total_row, column=7, value=float(total_interest)).font = Font(bold=True)
    sheet.cell(row=total_row, column=8, value=float(total_amount)).font = Font(bold=True)

    _finish_sheet(sheet, currency_columns=[6, 7, 8], date_columns=[5])

    filename = f"Insolutos_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return _excel_response(workbook, filename)


# ============================================================
# INFORME DIVIDENDOS PAGADOS
# ============================================================

@login_required
@require_GET
def report_paid_installments_excel(request):
    date_from = _date_param(request, "fecha_desde")
    date_to = _date_param(request, "fecha_hasta")
    paid = _status_paid()

    queryset = LoanInstallment.objects.none()

    if paid:
        queryset = (
            LoanInstallment.objects
            .filter(is_active=True, status=paid, loan__is_active=True)
            .select_related("loan", "loan__person", "collection_method")
        )

        if date_from:
            queryset = queryset.filter(due_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(due_date__lte=date_to)

        queryset = queryset.order_by("loan__person_id", "installment_number", "id")

    installments = list(queryset)
    employee_codes = _employee_codes([item.loan.person_id for item in installments if item.loan.person_id])

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Dividendos pagados"

    headers = ["Fecha pago", "Tipo pago", "Código funcionario", "RUT", "Nombre", "Cuota", "Monto"]
    _prepare_sheet(sheet, "INFORME DE DIVIDENDOS PAGADOS", _date_range_text(date_from, date_to), headers)

    total_amount = Decimal("0")

    for row_number, installment in enumerate(installments, start=5):
        amount = Decimal(installment.amount or 0)
        total_amount += amount

        values = [
            installment.due_date,
            installment.collection_method.name if installment.collection_method else "Dividendo pagado",
            employee_codes.get(installment.loan.person_id, ""),
            _person_rut(installment.loan.person),
            _person_full_name(installment.loan.person),
            int(installment.installment_number or 0),
            float(amount),
        ]

        for column, value in enumerate(values, start=1):
            sheet.cell(row=row_number, column=column, value=value)

    total_row = sheet.max_row + 1
    sheet.cell(row=total_row, column=6, value="Total").font = Font(bold=True)
    sheet.cell(row=total_row, column=7, value=float(total_amount)).font = Font(bold=True)

    _finish_sheet(sheet, currency_columns=[7], date_columns=[1])

    filename = f"Dividendos_pagados_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return _excel_response(workbook, filename)


# ============================================================
# INFORME INTERESES DE SALDOS
# ============================================================

@login_required
@require_GET
def report_interest_balances_excel(request):
    try:
        date_from = _date_param(request, "desde", required=True)
        date_to = _date_param(request, "hasta", required=True)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain; charset=utf-8")

    if date_from > date_to:
        return HttpResponse(
            "La fecha desde no puede ser mayor que la fecha hasta.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )

    installments = list(
        LoanInstallment.objects
        .filter(
            is_active=True,
            loan__is_active=True,
            due_date__range=(date_from, date_to),
            interest__gt=0,
        )
        .select_related("loan", "loan__person")
        .order_by("loan__person_id", "installment_number", "id")
    )

    employee_codes = _employee_codes([item.loan.person_id for item in installments if item.loan.person_id])

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Intereses saldos"

    headers = ["ID préstamo", "Código funcionario", "RUT", "Nombre", "Cuota", "Fecha dividendo", "Interés"]
    _prepare_sheet(
        sheet,
        "INFORME DE INTERESES OBTENIDOS DE SALDOS",
        _date_range_text(date_from, date_to),
        headers,
    )

    total_interest = Decimal("0")

    for row_number, installment in enumerate(installments, start=5):
        interest = Decimal(installment.interest or 0)
        total_interest += interest

        values = [
            installment.loan_id,
            employee_codes.get(installment.loan.person_id, ""),
            _person_rut(installment.loan.person),
            _person_full_name(installment.loan.person),
            int(installment.installment_number or 0),
            installment.due_date,
            float(interest),
        ]

        for column, value in enumerate(values, start=1):
            sheet.cell(row=row_number, column=column, value=value)

    total_row = sheet.max_row + 1
    sheet.cell(row=total_row, column=6, value="Total interés").font = Font(bold=True)
    sheet.cell(row=total_row, column=7, value=float(total_interest)).font = Font(bold=True)

    _finish_sheet(sheet, currency_columns=[7], date_columns=[6])

    filename = (
        f"Intereses_saldos_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}_"
        f"{timezone.localtime().strftime('%H%M%S')}.xlsx"
    )
    return _excel_response(workbook, filename)
