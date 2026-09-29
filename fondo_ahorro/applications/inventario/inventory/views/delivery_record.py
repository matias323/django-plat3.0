from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from core.models.person import Person

from ..models import (
    DeliveryRecord, DeliveryRecordDocument, DeliveryRecordProduct, DeliveryRecordStatus, DeliveryRecordType, Fund,
    Product, Subclass,
)
from ..utils import (
    audit_save, can_edit_inventory, document_url, is_inventory_superadmin, person_full_name, person_rut,
    save_uploaded_document,
)
from .inventory import person_query
from .product import next_role_number, update_product_depreciation


def ensure_catalogs(user=None):
    def ensure(model, pk, name):
        obj = model.objects.filter(pk=pk).first()
        if obj:
            return obj
        obj = model(pk=pk, name=name)
        obj.is_active = True
        return audit_save(obj, user)

    outgoing = ensure(DeliveryRecordType, 1, "Salida")
    incoming = ensure(DeliveryRecordType, 2, "Entrada")
    current = ensure(DeliveryRecordStatus, 1, "Vigente")
    cancelled = ensure(DeliveryRecordStatus, 2, "Anulada")
    return outgoing, incoming, current, cancelled


def next_record_number():
    return (DeliveryRecord.objects.aggregate(last=Max("record_number"))["last"] or 0) + 1


@login_required
def delivery_records_data(request):
    ensure_catalogs(request.user)
    data = []
    queryset = DeliveryRecord.objects.filter(is_active=True).select_related("record_type", "status", "lender")
    for record in queryset:
        badge = '<span class="badge bg-danger">Salida</span>' if record.record_type_id == 1 else (
            '<span class="badge bg-success">Entrada</span>'
        )
        data.append({
            "number": record.record_number,
            "date": record.record_date.strftime("%d-%m-%Y"),
            "type": badge,
            "area": record.area,
            "lender": person_full_name(record.lender) if record.lender_id else "-",
            "products": record.product_links.filter(is_active=True).count(),
            "status": record.status.name,
            "actions": (
                f'<button type="button" class="btn btn-sm btn-primary btn-record-view" data-id="{record.id}">'
                '<span class="bi bi-eye"></span></button>'
            ),
        })
    return JsonResponse({"data": data})


@login_required
def delivery_record_modal(request):
    if not can_edit_inventory(request):
        return render(request, "inventario/modal_delivery_record.html", {"permission_denied": True})
    ensure_catalogs(request.user)
    return render(request, "inventario/modal_delivery_record.html", {
        "types": DeliveryRecordType.objects.filter(is_active=True).order_by("id"),
    })


@login_required
def search_lenders(request):
    results = [
        {"id": person.id, "text": f"{person_full_name(person)} | {person_rut(person)}"}
        for person in person_query(request.GET.get("q", ""))
    ]
    return JsonResponse({"results": results})


@login_required
def search_outgoing_products(request):
    term = (request.GET.get("q", "") or "").strip()
    queryset = Product.objects.filter(status=Product.STATUS_ACTIVE, is_active=True).exclude(fund__name__iexact="ARRIENDO")
    if term:
        query = (
            Q(name__icontains=term) | Q(bcu_number__icontains=term) | Q(serial_number__icontains=term) |
            Q(brand__icontains=term) | Q(model__icontains=term)
        )
        if term.isdigit():
            query |= Q(role_number=int(term))
        queryset = queryset.filter(query)

    results = [{
        "id": product.id,
        "text": (
            f"Rol {product.role_number} - {product.name} | {product.brand or ''} {product.model or ''} | "
            f"Serial: {product.serial_number or ''}"
        ),
    } for product in queryset[:30]]
    return JsonResponse({"results": results})


@login_required
@transaction.atomic
def delivery_record_save(request):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)

    try:
        _, _, current, _ = ensure_catalogs(request.user)
        type_id = int(request.POST.get("record_type", 0) or 0)
        record_date_raw = request.POST.get("record_date")
        area = (request.POST.get("area", "") or "").strip()
        lender_id = int(request.POST.get("lender_id", 0) or 0) or None
        observation = (request.POST.get("observation", "") or "").strip() or None

        if type_id not in (1, 2):
            raise ValueError("Debe seleccionar Entrada o Salida.")
        if not record_date_raw or not area:
            raise ValueError("Debe ingresar fecha y área.")

        record_date = date.fromisoformat(record_date_raw)
        if lender_id and not Person.objects.filter(pk=lender_id, is_active=True).exists():
            raise ValueError("El prestamista seleccionado no existe o está inactivo.")

        record = DeliveryRecord(
            record_number=next_record_number(), record_date=record_date, record_type_id=type_id, status=current,
            area=area, lender_id=lender_id, observation=observation,
        )
        audit_save(record, request.user)

        if type_id == 1:
            product_ids = [int(value) for value in request.POST.getlist("outgoing_products[]") if str(value).isdigit()]
            if not product_ids:
                raise ValueError("Debe seleccionar al menos un producto de salida.")

            products = list(
                Product.objects
                .select_for_update()
                .filter(id__in=product_ids)
            )

            if len(products) != len(set(product_ids)):
                raise ValueError("Uno de los productos seleccionados no existe.")

            for product in products:
                if product.status != Product.STATUS_ACTIVE or not product.is_active:
                    raise ValueError("Uno de los productos seleccionados no está disponible.")
                if product.fund and product.fund.name.strip().upper() == "ARRIENDO":
                    raise ValueError("No se puede registrar como salida un producto externo o en arriendo.")
                if not product.use_start_date:
                    product.use_start_date = record_date
                    audit_save(product, request.user)
                    update_product_depreciation(product)
                audit_save(DeliveryRecordProduct(record=record, product=product), request.user)

        else:
            names = request.POST.getlist("entry_name[]")
            if not names:
                raise ValueError("Debe ingresar al menos un producto.")

            rental = Fund.objects.filter(name__iexact="ARRIENDO").first()
            if not rental:
                rental = Fund(name="ARRIENDO")
                audit_save(rental, request.user)

            brands = request.POST.getlist("entry_brand[]")
            models = request.POST.getlist("entry_model[]")
            sizes = request.POST.getlist("entry_size[]")
            colors = request.POST.getlist("entry_color[]")
            serials = request.POST.getlist("entry_serial[]")
            bcus = request.POST.getlist("entry_bcu[]")
            saps = request.POST.getlist("entry_sap[]")
            subclasses = request.POST.getlist("entry_subclass[]")
            observations = request.POST.getlist("entry_observation[]")

            for index, raw_name in enumerate(names):
                name = (raw_name or "").strip()
                subclass_id = int(subclasses[index] if index < len(subclasses) and subclasses[index] else 0)
                subclass = Subclass.objects.filter(pk=subclass_id, is_active=True).first()
                if not name:
                    raise ValueError(f"Producto #{index + 1}: falta el nombre.")
                if not subclass:
                    raise ValueError(f"Producto #{index + 1}: falta la subclase.")

                bcu = (bcus[index] if index < len(bcus) else "").strip() or None
                sap = (saps[index] if index < len(saps) else "").strip() or None
                if bcu and Product.objects.filter(bcu_number=bcu).exists():
                    raise ValueError(f'El número BCU "{bcu}" ya existe.')
                if sap and Product.objects.filter(sap_number=sap).exists():
                    raise ValueError(f'El número SAP "{sap}" ya existe.')

                product = Product(
                    name=name,
                    brand=(brands[index] if index < len(brands) else "").strip() or None,
                    model=(models[index] if index < len(models) else "").strip() or None,
                    size=(sizes[index] if index < len(sizes) else "") or None,
                    color=(colors[index] if index < len(colors) else "").strip() or None,
                    serial_number=(serials[index] if index < len(serials) else "").strip() or None,
                    bcu_number=bcu,
                    sap_number=sap,
                    role_number=next_role_number(),
                    fund=rental,
                    subclass=subclass,
                    stock=1,
                    acquisition_date=record_date,
                    use_start_date=None,
                    initial_value=1,
                    current_value=1,
                    useful_life_years=subclass.useful_life_years,
                    useful_life_months=subclass.useful_life_years * 12,
                    status=Product.STATUS_ACTIVE,
                    observation=(observations[index] if index < len(observations) else "").strip() or None,
                )
                audit_save(product, request.user)
                audit_save(DeliveryRecordProduct(record=record, product=product), request.user)
                update_product_depreciation(product)

        for uploaded in request.FILES.getlist("record_documents"):
            document = save_uploaded_document(
                request, uploaded, "Inventario - Acta de Entrega", f"actas/{record.record_number}",
            )
            audit_save(DeliveryRecordDocument(record=record, document=document), request.user)

        return JsonResponse({
            "status": "success", "message": "Acta de entrega guardada correctamente.", "id_record": record.id,
        })
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
def delivery_record_detail(request, pk):
    ensure_catalogs(request.user)
    record = get_object_or_404(
        DeliveryRecord.objects.select_related("record_type", "status", "lender"), pk=pk,
    )
    products = [
        link.product
        for link in record.product_links.filter(is_active=True).select_related(
            "product", "product__fund", "product__subclass", "product__subclass__asset_class",
            "product__subclass__inventory_class",
        )
    ]
    documents = [
        {
            "name": link.document.document_name,
            "url": document_url(link.document),
            "date": getattr(link.document, "creation_date", None),
        }
        for link in record.document_links.filter(is_active=True).select_related("document")
    ]
    return render(request, "inventario/modal_delivery_record_detail.html", {
        "record": record,
        "products": products,
        "documents": documents,
        "can_edit": can_edit_inventory(request),
        "can_cancel": is_inventory_superadmin(request),
        "lender_name": person_full_name(record.lender) if record.lender_id else "",
    })


@login_required
@transaction.atomic
def delivery_record_document_upload(request, pk):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)
    try:
        record = get_object_or_404(DeliveryRecord, pk=pk)
        files = request.FILES.getlist("record_documents")
        if not files:
            raise ValueError("Debe seleccionar al menos un documento.")
        for uploaded in files:
            document = save_uploaded_document(
                request, uploaded, "Inventario - Acta de Entrega", f"actas/{record.record_number}",
            )
            audit_save(DeliveryRecordDocument(record=record, document=document), request.user)
        return JsonResponse({"status": "success", "message": "Documento(s) agregado(s) correctamente."})
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
@transaction.atomic
def delivery_record_cancel(request, pk):
    if not is_inventory_superadmin(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos para anular actas."}, status=403)
    try:
        _, _, _, cancelled = ensure_catalogs(request.user)
        record = DeliveryRecord.objects.select_for_update().get(pk=pk)
        if not record.is_active or record.status_id == cancelled.id:
            raise ValueError("El acta de entrega ya se encuentra anulada.")

        product_ids = list(record.product_links.filter(is_active=True).values_list("product_id", flat=True))
        Product.objects.filter(id__in=product_ids).update(status=Product.STATUS_INACTIVE, is_active=False)
        record.product_links.filter(is_active=True).update(is_active=False)
        record.status = cancelled
        record.is_active = False
        audit_save(record, request.user)
        return JsonResponse({
            "status": "success",
            "message": "El acta de entrega y sus productos asociados fueron anulados correctamente.",
        })
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})