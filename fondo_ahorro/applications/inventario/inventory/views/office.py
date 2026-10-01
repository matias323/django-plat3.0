from datetime import date
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..models import Office, OfficePerson, OfficeProduct, Product, ProductAssignment
from ..utils import audit_save, can_edit_inventory, clp, date_cl, person_full_name, person_rut
from .inventory import person_query


def sync_office_products_from_people(office_id, user=None):
    """
    Sincroniza los productos de una oficina con las asignaciones activas
    de las personas que actualmente pertenecen a esa oficina.

    - Agrega productos nuevos asignados a personas de la oficina.
    - Quita productos que antes estuvieron asignados a esas personas,
      pero cuya asignación ya no está activa.
    - Si un producto cambia a una persona de otra oficina, el vínculo
      del producto se mueve a la oficina correcta.
    - Los productos agregados manualmente que nunca estuvieron asignados
      a una persona de esta oficina no se eliminan.
    """
    office_id = int(office_id or 0)
    if not office_id:
        return

    person_ids = list(
        OfficePerson.objects.filter(
            office_id=office_id,
            is_active=True,
        ).values_list("person_id", flat=True)
    )

    if not person_ids:
        return

    active_product_ids = set(
        ProductAssignment.objects.filter(
            person_id__in=person_ids,
            is_active=True,
            product__status=Product.STATUS_ACTIVE,
            product__is_active=True,
        ).values_list("product_id", flat=True)
    )

    historical_product_ids = set(
        ProductAssignment.objects.filter(
            person_id__in=person_ids,
        ).values_list("product_id", flat=True)
    )

    stale_product_ids = historical_product_ids - active_product_ids

    if stale_product_ids:
        OfficeProduct.objects.filter(
            office_id=office_id,
            product_id__in=stale_product_ids,
        ).delete()

    for product_id in active_product_ids:
        link = OfficeProduct.objects.filter(product_id=product_id).first()

        if link:
            changed = False

            if link.office_id != office_id:
                link.office_id = office_id
                changed = True

            if not link.is_active:
                link.is_active = True
                changed = True

            if changed:
                audit_save(link, user)

            continue

        audit_save(
            OfficeProduct(
                office_id=office_id,
                product_id=product_id,
                is_active=True,
            ),
            user,
        )


@login_required
def offices_list(request):
    data = [{"id": office.id, "name": office.name} for office in Office.objects.filter(is_active=True).order_by("name")]
    return JsonResponse({"status": "success", "data": data})


@login_required
def office_products_data(request):
    office_id = int(request.POST.get("office_id", 0) or 0)
    data = []

    if office_id:
        sync_office_products_from_people(office_id, request.user)

        links = OfficeProduct.objects.filter(office_id=office_id, is_active=True).select_related(
            "product", "product__fund", "product__subclass", "product__subclass__asset_class",
            "product__subclass__inventory_class",
        ).order_by("product__role_number")
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
                "serial": product.serial_number or "",
                "fund": product.fund.name if product.fund_id else "",
                "asset_class": product.subclass.asset_class.name,
                "class": product.subclass.inventory_class.name,
                "subclass": product.subclass.name,
                "current_value": clp(product.current_value),
                "status": status,
                "actions": (
                    f'<button type="button" class="btn btn-sm btn-primary btn-product" data-id="{product.id}">'
                    '<span class="bi bi-eye"></span></button> '
                    f'<button type="button" class="btn btn-sm btn-danger btn-office-product-remove" data-id="{product.id}">'
                    '<span class="bi bi-trash"></span></button>'
                ),
            })
    return JsonResponse({"data": data})


@login_required
def office_people_data(request):
    office_id = int(request.POST.get("office_id", 0) or 0)
    data = []
    if office_id:
        for link in OfficePerson.objects.filter(office_id=office_id, is_active=True).select_related("person"):
            total = ProductAssignment.objects.filter(
                person=link.person,
                is_active=True,
                product__status=Product.STATUS_ACTIVE,
                product__is_active=True,
            ).values("product_id").distinct().count()
            data.append({
                "person": person_full_name(link.person),
                "rut": person_rut(link.person),
                "products": total,
                "actions": (
                    f'<button type="button" class="btn btn-sm btn-danger btn-office-person-remove" '
                    f'data-id="{link.person_id}"><span class="bi bi-trash"></span></button>'
                ),
            })
    return JsonResponse({"data": data})


@login_required
def search_office_products(request):
    term = (request.GET.get("q", "") or "").strip()
    queryset = Product.objects.filter(status=Product.STATUS_ACTIVE).filter(
        Q(office_link__isnull=True) | Q(office_link__is_active=False)
    )
    if term:
        query = (
            Q(name__icontains=term) | Q(brand__icontains=term) | Q(model__icontains=term) |
            Q(bcu_number__icontains=term) | Q(serial_number__icontains=term)
        )
        if term.isdigit():
            query |= Q(role_number=int(term))
        queryset = queryset.filter(query)

    results = [{
        "id": product.id,
        "text": (
            f"{product.name} | Rol: {product.role_number} | BCU: {product.bcu_number or ''} | "
            f"Serial: {product.serial_number or ''}"
        ),
    } for product in queryset[:30]]
    return JsonResponse({"results": results})


@login_required
def search_office_people(request):
    office_id = int(request.GET.get("office_id", 0) or 0)
    if not office_id:
        return JsonResponse({"results": []})

    results = []
    for person in person_query(request.GET.get("q", "")):
        active_elsewhere = OfficePerson.objects.filter(person=person, is_active=True).exclude(office_id=office_id).exists()
        current = OfficePerson.objects.filter(person=person, office_id=office_id, is_active=True).exists()
        if not active_elsewhere and not current:
            results.append({"id": person.id, "text": f"{person_full_name(person)} | RUT: {person_rut(person)}"})
    return JsonResponse({"results": results})


@login_required
@transaction.atomic
def office_product_update(request):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)
    try:
        office_id = int(request.POST.get("office_id", 0) or 0)
        product_id = int(request.POST.get("product_id", 0) or 0)
        action = request.POST.get("action", "add")
        if not office_id or not product_id:
            raise ValueError("Debe seleccionar oficina y producto.")

        if action == "remove":
            product_link = OfficeProduct.objects.select_for_update().filter(
                office_id=office_id,
                product_id=product_id,
            ).first()

            if not product_link:
                raise ValueError("El producto ya no se encuentra asociado a esta oficina.")

            active_assignments = list(
                ProductAssignment.objects.select_for_update().filter(
                    product_id=product_id,
                    is_active=True,
                )
            )

            for assignment in active_assignments:
                assignment.is_active = False
                audit_save(assignment, request.user)

            product_link.delete()

            if active_assignments:
                return JsonResponse({
                    "status": "success",
                    "message": (
                        "Producto quitado de la oficina y persona desvinculada "
                        "del producto correctamente."
                    ),
                })

            return JsonResponse({
                "status": "success",
                "message": "Producto quitado de la oficina correctamente.",
            })
        else:
            existing = OfficeProduct.objects.filter(product_id=product_id, is_active=True).exclude(
                office_id=office_id
            ).select_related("office").first()
            if existing:
                raise ValueError(f"Este producto ya está asociado a la oficina: {existing.office.name}")
            link, _ = OfficeProduct.objects.get_or_create(office_id=office_id, product_id=product_id)
            link.is_active = True
            audit_save(link, request.user)

        return JsonResponse({"status": "success", "message": "Oficina actualizada correctamente."})
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
@transaction.atomic
def office_person_update(request):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)
    try:
        office_id = int(request.POST.get("office_id", 0) or 0)
        person_id = int(request.POST.get("person_id", 0) or 0)
        action = request.POST.get("action", "add")
        if not office_id or not person_id:
            raise ValueError("Debe seleccionar oficina y persona.")

        if action == "remove":
            assigned = ProductAssignment.objects.filter(person_id=person_id, is_active=True).values_list(
                "product_id", flat=True
            )
            OfficeProduct.objects.filter(office_id=office_id, product_id__in=assigned).delete()
            OfficePerson.objects.filter(office_id=office_id, person_id=person_id).update(is_active=False)
            return JsonResponse({"status": "success", "message": "Persona quitada correctamente."})

        elsewhere = OfficePerson.objects.filter(person_id=person_id, is_active=True).exclude(
            office_id=office_id
        ).select_related("office").first()
        if elsewhere:
            raise ValueError(f"Esta persona ya está asociada a la oficina: {elsewhere.office.name}")

        link, _ = OfficePerson.objects.get_or_create(
            office_id=office_id, person_id=person_id, defaults={"assignment_date": date.today()},
        )
        link.assignment_date = date.today()
        link.is_active = True
        audit_save(link, request.user)

        product_ids = list(ProductAssignment.objects.filter(
            person_id=person_id, is_active=True, product__status=Product.STATUS_ACTIVE,
        ).values_list("product_id", flat=True))

        for product_id in product_ids:
            if OfficeProduct.objects.filter(product_id=product_id, is_active=True).exclude(office_id=office_id).exists():
                continue
            product_link, _ = OfficeProduct.objects.get_or_create(office_id=office_id, product_id=product_id)
            product_link.is_active = True
            audit_save(product_link, request.user)

        return JsonResponse({"status": "success", "message": "Persona agregada correctamente.", "ids": product_ids})
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc), "ids": []})


@login_required
@transaction.atomic
def office_sync(request):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)

    try:
        office_id = int(request.POST.get("office_id", 0) or 0)

        if not office_id:
            raise ValueError("Oficina inválida.")

        sync_office_products_from_people(office_id, request.user)

        return JsonResponse({
            "status": "success",
            "message": "Oficina sincronizada correctamente.",
        })
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
def office_export(request, pk):
    office = Office.objects.get(pk=pk)
    products = Product.objects.filter(
        office_link__office=office, office_link__is_active=True,
    ).select_related("fund", "subclass").order_by("role_number")
    book_1 = [product for product in products if product.book != 2]
    book_2 = [product for product in products if product.book == 2]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Planilla mural"
    sheet.merge_cells("A1:L1")
    sheet["A1"] = "CARABINEROS DE CHILE"
    sheet.merge_cells("A2:L2")
    sheet["A2"] = "CÓDIGO ORGANIZACIONAL : 2363200000"
    sheet.merge_cells("A3:L3")
    sheet["A3"] = "PLANILLA MURAL DE INVENTARIOS"
    sheet.merge_cells("A4:L4")
    sheet["A4"] = f"NOMBRE DE LA DEPENDENCIA: {office.name.upper()}"

    for cell in ("A1", "A2", "A3"):
        sheet[cell].alignment = Alignment(horizontal="center", vertical="center")
    for row in range(1, 5):
        sheet[f"A{row}"].font = Font(bold=True)

    headers = [
        "Rol", "NRO. SAP", "DESCRIPCIÓN", "CARACTERÍSTICAS", "NRO. SERIE", "NRO. BCU", "FONDOS",
        "O/D NRO.", "FECHA O/D", "FECHA PUESTA EN SERVICIO", "VIDA ÚTIL", "OBSERVACIONES",
    ]
    row = 5
    for column, value in enumerate(headers, 1):
        sheet.cell(row=row, column=column, value=value)

    thin = Side(style="thin", color="000000")
    for cell in sheet[row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9D9D9")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    row += 1

    def append_product(product, role_value):
        nonlocal row
        characteristics = (
            f" MARCA: {product.brand or ''} - MODELO: {product.model or ''} - COLOR: {product.color or ''} - "
            f" TAMAÑO: {product.size or ''}"
        ).upper()
        values = [
            role_value,
            product.sap_number or "",
            (product.name or "").upper(),
            characteristics,
            str(product.serial_number or ""),
            product.bcu_number or "",
            product.fund.name if product.fund_id else "",
            "",
            date_cl(product.acquisition_date),
            date_cl(product.use_start_date),
            product.useful_life_years,
            (product.observation or "").upper(),
        ]
        for column, value in enumerate(values, 1):
            cell = sheet.cell(row=row, column=column, value=value)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=column in (3, 4))
        row += 1

    for product in book_1:
        append_product(product, product.role_number)

    if book_2:
        row += 1
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=12)
        cell = sheet.cell(row=row, column=1, value="ESPECIES REGISTRADAS EN EL LIBRO NRO. 2 DE INVENTARIO")
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        row += 1
        for index, product in enumerate(book_2, 1):
            append_product(product, index)

    row += 1
    sheet.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)
    sheet.cell(row=row, column=5, value=f"Santiago, {date.today().strftime('%d-%m-%Y')}").alignment = Alignment(
        horizontal="center"
    )
    row += 5
    signatures = [
        (1, 3, "JEFE COMISIÓN INVENTARIO"),
        (5, 7, "PRESIDENTE COMISIÓN INVENTARIO"),
        (11, 12, "MIEMBRO COMISIÓN INVENTARIO"),
    ]
    for start, end, text in signatures:
        sheet.merge_cells(start_row=row, start_column=start, end_row=row, end_column=end)
        sheet.cell(row=row, column=start, value="_______________________________").alignment = Alignment(horizontal="center")
        sheet.merge_cells(start_row=row + 1, start_column=start, end_row=row + 1, end_column=end)
        cell = sheet.cell(row=row + 1, column=start, value=text)
        cell.alignment = Alignment(horizontal="center")
        cell.font = Font(bold=True)

    widths = [5, 14, 28, 70, 18, 18, 12, 14, 15, 25, 12, 22]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    sheet.freeze_panes = "A6"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = f"Planilla_mural_oficina_{office.id}_{date.today().strftime('%Y%m%d')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
