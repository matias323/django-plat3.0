from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from core.models.person import Person

from ..models import Product, ProductAssignment, Subclass
from ..utils import (
    accounting_account, can_edit_inventory, can_view_inventory, clp, date_cl, person_full_name, person_rut,
    query_communes,
)
from .product import update_all_depreciations


def person_query(term):
    term = (term or "").strip()
    if len(term) < 2:
        return Person.objects.none()

    queryset = Person.objects.filter(is_active=True)
    for item in [value for value in term.split() if value]:
        queryset = queryset.filter(
            Q(first_name__icontains=item) | Q(second_name__icontains=item) |
            Q(last_name_1__icontains=item) | Q(last_name_2__icontains=item) |
            Q(rut__icontains=item) | Q(dv__icontains=item)
        )

    return queryset.order_by("last_name_1", "last_name_2", "first_name", "second_name")[:20]


@login_required
def inventory(request):
    if not can_view_inventory(request):
        return render(request, "inventario/inventory.html", {"permission_denied": True})
    return render(request, "inventario/inventory.html", {"can_edit": can_edit_inventory(request)})


@login_required
def products_data(request):
    update_all_depreciations()
    draw = int(request.POST.get("draw", 1) or 1)
    start = int(request.POST.get("start", 0) or 0)
    length = int(request.POST.get("length", 25) or 25)
    search = (request.POST.get("search[value]", "") or "").strip()
    depreciation_filter = (request.POST.get("depreciation_filter", "") or "").strip()

    base = Product.objects.exclude(status=Product.STATUS_INACTIVE).select_related(
        "fund", "invoice", "subclass", "subclass__asset_class", "subclass__inventory_class",
    )
    total = base.count()
    queryset = base

    if search:
        query = (
            Q(name__icontains=search) | Q(brand__icontains=search) | Q(model__icontains=search) |
            Q(bcu_number__icontains=search) | Q(sap_number__icontains=search) | Q(serial_number__icontains=search) |
            Q(fund__name__icontains=search) | Q(subclass__name__icontains=search) |
            Q(subclass__asset_class__name__icontains=search) | Q(subclass__inventory_class__name__icontains=search)
        )
        if search.isdigit():
            query |= Q(role_number=int(search)) | Q(invoice__invoice_number=int(search))
        lowered = search.lower()
        if "activo" in lowered:
            query |= Q(status=Product.STATUS_ACTIVE)
        if "de baja" in lowered:
            query |= Q(status__in=[Product.STATUS_WRITTEN_OFF, Product.STATUS_WRITTEN_OFF_BOOK_2])
        if "libro 2" in lowered:
            query |= Q(book=2)
        queryset = queryset.filter(query)

    today = date.today()
    if depreciation_filter == "unassigned":
        queryset = queryset.exclude(assignments__is_active=True)
    elif depreciation_filter == "soon":
        queryset = queryset.filter(current_value__gt=1, end_date__gt=today, end_date__lte=today + timedelta(days=184))
    elif depreciation_filter == "depreciated":
        queryset = queryset.filter(Q(current_value__lte=1) | Q(end_date__lte=today))
    elif depreciation_filter == "written_off":
        queryset = queryset.filter(status=Product.STATUS_WRITTEN_OFF)
    elif depreciation_filter == "book2":
        queryset = queryset.filter(book=2)

    filtered = queryset.distinct().count()
    rows = []
    for product in queryset.distinct().order_by("-acquisition_date", "-id")[start:start + length]:
        row_class = ""
        if product.current_value <= 1:
            row_class = "inventory-depreciated"
        elif product.end_date and product.end_date <= today + timedelta(days=184):
            row_class = "inventory-soon"

        status = {
            Product.STATUS_ACTIVE: '<span class="badge bg-primary">Activo</span>',
            Product.STATUS_WRITTEN_OFF: '<span class="badge bg-warning text-dark">De baja</span>',
            Product.STATUS_WRITTEN_OFF_BOOK_2: '<span class="badge bg-warning text-dark">De baja - Libro 2</span>',
            Product.STATUS_INACTIVE: '<span class="badge bg-secondary">Inactivo</span>',
        }.get(product.status, '<span class="badge bg-secondary">Estado desconocido</span>')

        rows.append({
            "DT_RowClass": row_class,
            "name": product.name,
            "brand": product.brand or "",
            "role": product.role_number,
            "asset_class": product.subclass.asset_class.name,
            "class": product.subclass.inventory_class.name,
            "fund": product.fund.name if product.fund_id else "",
            "invoice": product.invoice.invoice_number if product.invoice_id else "Sin factura",
            "stock": product.stock,
            "initial_value": clp(product.initial_value),
            "current_value": clp(product.current_value),
            "accumulated": clp(product.accumulated_depreciation),
            "acquisition_date": date_cl(product.acquisition_date),
            "status": status,
            "actions": (
                f'<button type="button" class="btn btn-sm btn-primary btn-product" data-id="{product.id}">'
                '<span class="bi bi-eye"></span></button>'
            ),
        })

    return JsonResponse({"draw": draw, "recordsTotal": total, "recordsFiltered": filtered, "data": rows})


@login_required
def person_products_data(request):
    person_id = int(request.POST.get("person_id", 0) or 0)
    data = []
    if person_id:
        links = ProductAssignment.objects.filter(person_id=person_id, is_active=True).select_related(
            "product", "product__fund", "product__subclass", "product__subclass__asset_class",
            "product__subclass__inventory_class",
        )
        for link in links:
            product = link.product
            status = '<span class="badge bg-success">Activo</span>' if product.status == 1 else (
                '<span class="badge bg-warning text-dark">De baja</span>'
            )
            data.append({
                "name": product.name,
                "brand": product.brand or "",
                "model": product.model or "",
                "role": product.role_number,
                "bcu": product.bcu_number or "",
                "sap": product.sap_number or "",
                "serial": product.serial_number or "",
                "fund": product.fund.name if product.fund_id else "",
                "asset_class": product.subclass.asset_class.name,
                "class": product.subclass.inventory_class.name,
                "subclass": product.subclass.name,
                "initial_value": clp(product.initial_value),
                "current_value": clp(product.current_value),
                "assignment_date": date_cl(link.assignment_date),
                "status": status,
                "actions": (
                    f'<button type="button" class="btn btn-sm btn-primary btn-product" data-id="{product.id}">'
                    '<span class="bi bi-eye"></span></button>'
                ),
            })
    return JsonResponse({"data": data})


@login_required
def search_people(request):
    results = [
        {"id": person.pk, "text": f"{person_full_name(person)} - {person_rut(person)}"}
        for person in person_query(request.GET.get("q", ""))
    ]
    return JsonResponse({"results": results})


@login_required
def search_subclasses(request):
    term = (request.GET.get("q", "") or "").strip()
    queryset = Subclass.objects.filter(
        is_active=True, inventory_class__is_active=True, asset_class__is_active=True,
    ).select_related("inventory_class", "asset_class")
    if term:
        queryset = queryset.filter(
            Q(name__icontains=term) | Q(inventory_class__name__icontains=term) | Q(asset_class__name__icontains=term)
        )

    results = []
    for subclass in queryset[:30]:
        account = accounting_account(subclass.accounting_account_id)
        results.append({
            "id": subclass.id,
            "text": f"{subclass.asset_class.name} / {subclass.inventory_class.name} / {subclass.name}",
            "subclass": subclass.name,
            "class": subclass.inventory_class.name,
            "asset_class": subclass.asset_class.name,
            "useful_life_years": subclass.useful_life_years,
            "accounting_account_name": account["name"],
            "accounting_account": account["number"],
        })
    return JsonResponse({"results": results})


@login_required
def search_communes(request):
    try:
        rows = query_communes(request.GET.get("q", ""))
        return JsonResponse({"results": [{"id": row["id"], "text": row["name"]} for row in rows]})
    except Exception as exc:
        return JsonResponse({"results": [], "error": str(exc)})
