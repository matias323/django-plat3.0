from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import BigIntegerField, ExpressionWrapper, F, Max, Sum
from django.http import JsonResponse
from django.shortcuts import render

from core.models.person import Person

from ..models import Fund, Invoice, Product, ProductAssignment, ProductDocument, Subclass
from ..utils import (
    audit_save, can_edit_inventory, clean_digits, document_url, person_full_name, person_rut, save_uploaded_document,
)


def _first_day_for_depreciation(value):
    if not value:
        return None
    if value.day >= 16:
        year = value.year + (1 if value.month == 12 else 0)
        month = 1 if value.month == 12 else value.month + 1
        return value.replace(year=year, month=month, day=1)
    return value.replace(day=1)


def _months_between(start, process):
    if not start or not process or process < start:
        return 0
    return ((process.year - start.year) * 12) + (process.month - start.month) + 1


def _is_rental(product):
    return bool(product.fund_id and product.fund and product.fund.name.strip().upper() == "ARRIENDO")


def update_product_depreciation(product, process_date=None):
    if not product.pk:
        return product

    if _is_rental(product):
        product.depreciation = 0
        product.accumulated_depreciation = 0
        product.end_date = None
        product.save(update_fields=["depreciation", "accumulated_depreciation", "end_date"])
        return product

    if not product.use_start_date:
        product.depreciation = 0
        product.accumulated_depreciation = 0
        product.current_value = product.initial_value
        product.end_date = None
        product.save(update_fields=["depreciation", "accumulated_depreciation", "current_value", "end_date"])
        return product

    if product.initial_value <= 0 or product.useful_life_months <= 0:
        return product

    start = _first_day_for_depreciation(product.use_start_date)
    process = _first_day_for_depreciation(process_date or date.today())
    months = min(_months_between(start, process), product.useful_life_months)
    residual = 1
    depreciable = max(product.initial_value - residual, 0)
    monthly = max(depreciable // product.useful_life_months, 1)
    accumulated = depreciable if months >= product.useful_life_months else min(monthly * months, depreciable)
    current = max(product.initial_value - accumulated, residual)

    index = start.month - 1 + (product.useful_life_months - 1)
    end_year = start.year + index // 12
    end_month = index % 12 + 1

    product.depreciation = monthly
    product.accumulated_depreciation = accumulated
    product.current_value = current
    product.end_date = date(end_year, end_month, 1)
    product.save(update_fields=["depreciation", "accumulated_depreciation", "current_value", "end_date"])
    return product


def update_all_depreciations():
    products = Product.objects.filter(
        status=Product.STATUS_ACTIVE, initial_value__gt=0, useful_life_months__gt=0,
    ).select_related("fund")
    for product in products:
        update_product_depreciation(product)


def next_role_number():
    return (Product.objects.aggregate(last=Max("role_number"))["last"] or 0) + 1


def normalize_unique(value):
    value = str(value or "").strip()
    return value or None


def recalculate_invoice_totals(invoice_id, user=None):
    """
    Recalcula el monto neto e IVA de una factura desde los productos
    actualmente asociados a ella.

    Se usa tanto al crear una factura como al crear/editar un producto.
    """
    if not invoice_id:
        return None

    invoice = Invoice.objects.select_for_update().filter(pk=invoice_id).first()
    if not invoice:
        return None

    product_total = ExpressionWrapper(
        F("initial_value") * F("stock"),
        output_field=BigIntegerField(),
    )

    net_amount = (
        Product.objects
        .filter(invoice_id=invoice_id)
        .aggregate(total=Sum(product_total))
        .get("total")
        or 0
    )

    vat_amount = int(
        (Decimal(int(net_amount)) * Decimal("0.19"))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )

    invoice.net_amount = int(net_amount)
    invoice.vat_amount = vat_amount
    audit_save(invoice, user)

    return invoice


@login_required
def product_modal(request):
    product_id = int(request.GET.get("id", 0) or 0)
    product = Product.objects.select_related(
        "fund", "invoice", "subclass", "subclass__asset_class", "subclass__inventory_class",
    ).filter(pk=product_id).first()
    can_edit = can_edit_inventory(request)

    if product_id and not product:
        return render(request, "inventario/modal_product.html", {"not_found": True, "can_edit": can_edit})
    if not product and not can_edit:
        return render(request, "inventario/modal_product.html", {"permission_denied": True, "can_edit": False})

    active_assignment = None
    documents = []
    invoice_documents = []
    if product:
        active_assignment = product.assignments.filter(is_active=True).select_related("person").first()
        documents = [
            {"name": link.document.document_name, "url": document_url(link.document)}
            for link in product.document_links.filter(is_active=True).select_related("document")
        ]
        if product.invoice_id:
            invoice_documents = [
                {"name": link.document.document_name, "url": document_url(link.document)}
                for link in product.invoice.document_links.filter(is_active=True).select_related("document")
            ]

    return render(request, "inventario/modal_product.html", {
        "product": product,
        "can_edit": can_edit,
        "funds": Fund.objects.filter(is_active=True).order_by("name"),
        "invoices": Invoice.objects.filter(is_active=True, status=Invoice.STATUS_CURRENT).order_by("-invoice_number"),
        "active_assignment": active_assignment,
        "assignment_name": person_full_name(active_assignment.person) if active_assignment else "",
        "assignment_rut": person_rut(active_assignment.person) if active_assignment else "",
        "documents": documents,
        "invoice_documents": invoice_documents,
        "next_role": product.role_number if product else next_role_number(),
        "size_choices": Product.SIZE_CHOICES,
    })


@login_required
@transaction.atomic
def product_save(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método inválido."}, status=405)

    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos para modificar productos."}, status=403)

    try:
        product_id = int(request.POST.get("id_product", 0) or 0)
        is_new = product_id == 0

        product = (
            Product.objects.select_for_update().filter(pk=product_id).first()
            if product_id else None
        )

        if product_id and not product:
            raise ValueError("El producto que intenta modificar no existe.")

        previous_invoice_id = product.invoice_id if product else None

        subclass = Subclass.objects.filter(
            pk=int(request.POST.get("id_subclass", 0) or 0),
            is_active=True,
        ).first()

        if not subclass:
            raise ValueError("Debe seleccionar una subclase válida.")

        name = (request.POST.get("name", "") or "").strip()
        initial_value = int(clean_digits(request.POST.get("initial_value", "0")) or 0)
        requested_stock = max(int(request.POST.get("stock", 1) or 1), 1)

        if not name:
            raise ValueError("Debe ingresar el nombre del producto.")

        if initial_value <= 0:
            raise ValueError("Debe ingresar un valor inicial válido.")

        bcu = normalize_unique(request.POST.get("bcu_number"))
        sap = normalize_unique(request.POST.get("sap_number"))
        serial = normalize_unique(request.POST.get("serial_number"))

        # Si se crean varias unidades, cada una será un producto independiente con stock 1.
        # BCU, SAP y Serial no se duplican entre las unidades.
        if is_new and requested_stock > 1:
            bcu = None
            sap = None
            serial = None

        if bcu and Product.objects.filter(bcu_number=bcu).exclude(pk=product.pk if product else None).exists():
            raise ValueError(f'El número BCU "{bcu}" ya existe.')

        if sap and Product.objects.filter(sap_number=sap).exclude(pk=product.pk if product else None).exists():
            raise ValueError(f'El número SAP "{sap}" ya existe.')

        fund_id = int(request.POST.get("id_fund", 0) or 0) or None
        invoice_id = int(request.POST.get("id_invoice", 0) or 0) or None
        acquisition_date = request.POST.get("acquisition_date") or date.today()
        use_start_date = request.POST.get("use_start_date") or None
        book = int(request.POST.get("book", 0) or 0) or None
        observation = (request.POST.get("observation", "") or "").strip() or None
        status = int(request.POST.get("status", Product.STATUS_ACTIVE) or Product.STATUS_ACTIVE)
        person_id = int(request.POST.get("assigned_person_id", 0) or 0)

        person = None
        if person_id:
            person = Person.objects.filter(pk=person_id, is_active=True).first()
            if not person:
                raise ValueError("La persona seleccionada no existe o está inactiva.")

        uploaded = request.FILES.get("product_file")
        created_products = []

        if is_new:
            # Cada unidad solicitada se transforma en una fila independiente.
            for _ in range(requested_stock):
                new_product = Product(
                    name=name,
                    brand=(request.POST.get("brand", "") or "").strip() or None,
                    model=(request.POST.get("model", "") or "").strip() or None,
                    size=request.POST.get("size") or None,
                    color=(request.POST.get("color", "") or "").strip() or None,
                    bcu_number=bcu,
                    sap_number=sap,
                    serial_number=serial,
                    subclass=subclass,
                    fund_id=fund_id,
                    invoice_id=invoice_id,
                    stock=1,
                    role_number=next_role_number(),
                    acquisition_date=acquisition_date,
                    use_start_date=use_start_date,
                    initial_value=initial_value,
                    current_value=initial_value,
                    useful_life_years=subclass.useful_life_years,
                    useful_life_months=subclass.useful_life_years * 12,
                    book=book,
                    observation=observation,
                    status=status,
                    is_active=status != Product.STATUS_INACTIVE,
                )

                audit_save(new_product, request.user)

                if person:
                    assignment_date = date.today()

                    # La primera asignación a una persona marca el comienzo de uso.
                    if not new_product.use_start_date:
                        new_product.use_start_date = assignment_date
                        audit_save(new_product, request.user)

                    audit_save(
                        ProductAssignment(
                            person=person,
                            product=new_product,
                            assignment_date=assignment_date,
                        ),
                        request.user,
                    )

                new_product = Product.objects.select_related("fund").get(pk=new_product.pk)
                update_product_depreciation(new_product)
                created_products.append(new_product)

            # Un documento cargado al crear varias unidades queda relacionado
            # con todas ellas, evitando guardar físicamente el mismo archivo N veces.
            if uploaded and created_products:
                first_product = created_products[0]
                document = save_uploaded_document(
                    request,
                    uploaded,
                    "Inventario - Producto",
                    f"productos/{first_product.role_number}",
                )

                for created_product in created_products:
                    audit_save(
                        ProductDocument(product=created_product, document=document),
                        request.user,
                    )

            if invoice_id:
                recalculate_invoice_totals(invoice_id, request.user)

            quantity = len(created_products)
            message = (
                "Producto guardado correctamente."
                if quantity == 1
                else f"{quantity} productos creados correctamente, cada uno con stock 1."
            )

            return JsonResponse({
                "status": "success",
                "message": message,
                "id_product": created_products[0].id,
                "created_products": [item.id for item in created_products],
                "created_count": quantity,
            })

        # ============================================================
        # EDICIÓN DE UN PRODUCTO EXISTENTE
        # ============================================================
        product.name = name
        product.brand = (request.POST.get("brand", "") or "").strip() or None
        product.model = (request.POST.get("model", "") or "").strip() or None
        product.size = request.POST.get("size") or None
        product.color = (request.POST.get("color", "") or "").strip() or None
        product.bcu_number = bcu
        product.sap_number = sap
        product.serial_number = serial
        product.subclass = subclass
        product.fund_id = fund_id
        product.invoice_id = invoice_id

        # Los productos individualizados siempre quedan con stock 1.
        product.stock = 1

        product.acquisition_date = acquisition_date
        product.use_start_date = use_start_date
        product.initial_value = initial_value
        product.useful_life_years = subclass.useful_life_years
        product.useful_life_months = subclass.useful_life_years * 12
        product.book = book
        product.observation = observation
        product.status = status
        product.is_active = status != Product.STATUS_INACTIVE
        audit_save(product, request.user)

        ProductAssignment.objects.filter(product=product, is_active=True).update(is_active=False)

        if person:
            assignment_date = date.today()

            # No reinicia la depreciación al cambiar el producto de persona.
            if not product.use_start_date:
                product.use_start_date = assignment_date
                audit_save(product, request.user)

            audit_save(
                ProductAssignment(
                    person=person,
                    product=product,
                    assignment_date=assignment_date,
                ),
                request.user,
            )

        if uploaded:
            document = save_uploaded_document(
                request,
                uploaded,
                "Inventario - Producto",
                f"productos/{product.role_number}",
            )
            audit_save(
                ProductDocument(product=product, document=document),
                request.user,
            )

        product = Product.objects.select_related("fund").get(pk=product.pk)
        update_product_depreciation(product)

        invoice_ids = {previous_invoice_id, product.invoice_id}
        for current_invoice_id in invoice_ids:
            if current_invoice_id:
                recalculate_invoice_totals(current_invoice_id, request.user)

        return JsonResponse({
            "status": "success",
            "message": "Producto guardado correctamente.",
            "id_product": product.id,
            "created_products": [product.id],
            "created_count": 1,
        })

    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})

