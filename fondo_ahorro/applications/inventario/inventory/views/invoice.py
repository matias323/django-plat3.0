from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from core.models.location import Commune
from core.models.person import Person, PersonAddress, PersonContact

from ..models import Fund, Invoice, InvoiceDocument, Product, Subclass
from ..utils import (
    audit_save, can_edit_inventory, clean_digits, clp, date_cl, document_url, format_rut,
    is_inventory_superadmin, person_full_name, save_uploaded_document,
)
from .product import next_role_number, recalculate_invoice_totals, update_product_depreciation


def _provider_by_rut(rut):
    return Person.objects.filter(rut=rut, is_active=True).first()


def _contact_value(person, kind):
    if not person:
        return ""

    queryset = PersonContact.objects.filter(person=person, state=1, is_active=True).select_related("contact_type")

    if kind == "phone":
        queryset = queryset.filter(
            Q(contact_type__name__icontains="tel") |
            Q(contact_type__name__icontains="fono") |
            Q(contact_type__name__icontains="móvil") |
            Q(contact_type__name__icontains="movil")
        )
    else:
        queryset = queryset.filter(
            Q(contact_type__name__icontains="correo") |
            Q(contact_type__name__icontains="email") |
            Q(contact_type__name__icontains="e-mail")
        )

    contact = queryset.order_by("id").first()
    return contact.value if contact else ""


def _active_address(person):
    if not person:
        return None
    return PersonAddress.objects.filter(person=person, state=1, is_active=True).select_related("commune").first()


@login_required
def invoices_data(request):
    data = []
    queryset = Invoice.objects.filter(is_active=True, status=Invoice.STATUS_CURRENT).select_related(
        "provider", "commune",
    ).annotate(total_products=Sum("products__stock"))

    for invoice in queryset:
        data.append({
            "number": invoice.invoice_number,
            "date": date_cl(invoice.invoice_date),
            "rut": format_rut(invoice.provider_rut, invoice.provider_dv),
            "provider": invoice.provider_name,
            "amount": clp(invoice.net_amount),
            "vat": clp(invoice.vat_amount),
            "products": invoice.total_products or 0,
            "actions": (
                f'<button type="button" class="btn btn-sm btn-primary btn-invoice-view" '
                f'data-id="{invoice.id}" title="Ver factura">'
                '<span class="bi bi-eye"></span>'
                '</button>'
            ),
        })
    return JsonResponse({"data": data})


@login_required
def invoice_modal(request):
    if not can_edit_inventory(request):
        return render(request, "inventario/modal_invoice.html", {"permission_denied": True})
    return render(request, "inventario/modal_invoice.html", {
        "funds": Fund.objects.filter(is_active=True).order_by("name"),
    })


@login_required
def provider_lookup(request):
    try:
        rut = int(clean_digits(request.GET.get("rut", "")) or 0)
        if rut <= 0:
            raise ValueError("RUT inválido.")

        person = _provider_by_rut(rut)
        if not person:
            return JsonResponse({"status": "success", "data": None})

        address = _active_address(person)
        last_invoice = Invoice.objects.filter(provider=person).select_related("commune").order_by("-id").first()

        phone = _contact_value(person, "phone") or (last_invoice.phone if last_invoice else "")
        email = _contact_value(person, "email") or (last_invoice.email if last_invoice else "")

        commune_id = address.commune_id if address else (last_invoice.commune_id if last_invoice else None)
        commune = address.commune.name if address else (last_invoice.commune.name if last_invoice else "")
        street = address.address if address else (last_invoice.address if last_invoice else "")
        number = address.number if address else (last_invoice.address_number if last_invoice else "")

        return JsonResponse({"status": "success", "data": {
            "id": person.id,
            "rut": person.rut,
            "dv": person.dv,
            "name": person_full_name(person),
            "phone": phone or "",
            "email": email or "",
            "commune_id": commune_id,
            "commune": commune or "",
            "address": street or "",
            "address_number": number or "",
            "address_block": last_invoice.address_block if last_invoice else "",
            "business_activity": last_invoice.business_activity if last_invoice else "",
        }})
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
@transaction.atomic
def invoice_save(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método inválido."}, status=405)
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos para crear facturas."}, status=403)

    try:
        number = int(request.POST.get("invoice_number", 0) or 0)
        rut = int(clean_digits(request.POST.get("provider_rut", "")) or 0)
        dv = (request.POST.get("provider_dv", "") or "").strip().upper()
        provider_name = (request.POST.get("provider_name", "") or "").strip()
        business_activity = (request.POST.get("business_activity", "") or "").strip()
        address = (request.POST.get("address", "") or "").strip()
        address_number = (request.POST.get("address_number", "") or "").strip()
        address_block = (request.POST.get("address_block", "") or "").strip() or None
        phone = clean_digits(request.POST.get("phone", ""))
        email = (request.POST.get("email", "") or "").strip()
        invoice_date = request.POST.get("invoice_date")
        payment_date = request.POST.get("payment_date") or None
        commune_id = int(request.POST.get("commune_id", 0) or 0)

        if number <= 0:
            raise ValueError("Debe ingresar el número de factura.")
        if Invoice.objects.filter(invoice_number=number).exists():
            raise ValueError(f"Ya existe una factura registrada con el número {number}.")
        if rut <= 0 or not dv or not provider_name or not business_activity or not address or not address_number:
            raise ValueError("Complete los datos obligatorios del proveedor.")
        if not invoice_date:
            raise ValueError("Debe ingresar la fecha de la factura.")

        commune = Commune.objects.filter(pk=commune_id, is_active=True).first()
        if not commune:
            raise ValueError("Debe seleccionar una comuna válida.")

        uploaded_files = request.FILES.getlist("invoice_documents")
        if not uploaded_files:
            raise ValueError("Debe adjuntar al menos un documento.")

        names = request.POST.getlist("product_name[]")
        if not names:
            raise ValueError("Debe agregar al menos un producto.")

        provider = _provider_by_rut(rut)
        invoice = Invoice(
            invoice_number=number,
            invoice_date=invoice_date,
            payment_date=payment_date,
            provider=provider,
            provider_rut=rut,
            provider_dv=dv,
            provider_name=provider_name,
            business_activity=business_activity,
            commune=commune,
            address=address,
            address_number=address_number,
            address_block=address_block,
            phone=phone or None,
            email=email or None,
            net_amount=int(clean_digits(request.POST.get("net_amount", "0")) or 0),
            vat_amount=int(clean_digits(request.POST.get("vat_amount", "0")) or 0),
            status=Invoice.STATUS_CURRENT,
        )
        audit_save(invoice, request.user)

        for uploaded in uploaded_files:
            document = save_uploaded_document(request, uploaded, "Inventario - Factura", f"facturas/{invoice.id}")
            audit_save(InvoiceDocument(invoice=invoice, document=document), request.user)

        brands = request.POST.getlist("product_brand[]")
        models = request.POST.getlist("product_model[]")
        sizes = request.POST.getlist("product_size[]")
        colors = request.POST.getlist("product_color[]")
        stocks = request.POST.getlist("product_stock[]")
        bcus = request.POST.getlist("product_bcu[]")
        saps = request.POST.getlist("product_sap[]")
        serials = request.POST.getlist("product_serial[]")
        subclasses = request.POST.getlist("product_subclass[]")
        funds = request.POST.getlist("product_fund[]")
        acquisition_dates = request.POST.getlist("product_acquisition_date[]")
        use_start_dates = request.POST.getlist("product_use_start_date[]")
        initial_values = request.POST.getlist("product_initial_value[]")
        books = request.POST.getlist("product_book[]")

        for index, raw_name in enumerate(names):
            name = (raw_name or "").strip()
            if not name:
                raise ValueError(f"Producto #{index + 1}: falta el nombre.")

            quantity = max(int(stocks[index] if index < len(stocks) and stocks[index] else 1), 1)
            subclass_id = int(subclasses[index] if index < len(subclasses) and subclasses[index] else 0)
            subclass = Subclass.objects.filter(pk=subclass_id, is_active=True).first()
            if not subclass:
                raise ValueError(f"Producto #{index + 1}: falta una subclase válida.")

            fund_id = int(funds[index] if index < len(funds) and funds[index] else 0)
            if fund_id <= 0:
                raise ValueError(f"Producto #{index + 1}: falta el fondo.")

            initial_value = int(clean_digits(initial_values[index] if index < len(initial_values) else "0") or 0)
            if initial_value <= 0:
                raise ValueError(f"Producto #{index + 1}: valor inicial inválido.")

            for _ in range(quantity):
                bcu = ((bcus[index] if index < len(bcus) else "").strip() or None) if quantity == 1 else None
                sap = ((saps[index] if index < len(saps) else "").strip() or None) if quantity == 1 else None
                serial = ((serials[index] if index < len(serials) else "").strip() or None) if quantity == 1 else None
                if bcu and Product.objects.filter(bcu_number=bcu).exists():
                    raise ValueError(f'El número BCU "{bcu}" ya existe.')
                if sap and Product.objects.filter(sap_number=sap).exists():
                    raise ValueError(f'El número SAP "{sap}" ya existe.')

                product = Product(
                    invoice=invoice,
                    name=name,
                    brand=(brands[index] if index < len(brands) else "").strip() or None,
                    model=(models[index] if index < len(models) else "").strip() or None,
                    size=(sizes[index] if index < len(sizes) else "") or None,
                    color=(colors[index] if index < len(colors) else "").strip() or None,
                    bcu_number=bcu,
                    sap_number=sap,
                    serial_number=serial,
                    fund_id=fund_id,
                    subclass=subclass,
                    stock=1,
                    role_number=next_role_number(),
                    acquisition_date=(
                        acquisition_dates[index]
                        if index < len(acquisition_dates) and acquisition_dates[index]
                        else date.today()
                    ),
                    use_start_date=(
                        use_start_dates[index]
                        if index < len(use_start_dates) and use_start_dates[index]
                        else None
                    ),
                    initial_value=initial_value,
                    current_value=initial_value,
                    useful_life_years=subclass.useful_life_years,
                    useful_life_months=subclass.useful_life_years * 12,
                    book=int(books[index] if index < len(books) and books[index] else 1),
                    status=Product.STATUS_ACTIVE,
                )
                audit_save(product, request.user)
                product = Product.objects.select_related("fund").get(pk=product.pk)
                update_product_depreciation(product)

        recalculate_invoice_totals(invoice.id, request.user)

        return JsonResponse({
            "status": "success",
            "message": "Factura, productos y documentos guardados correctamente.",
            "id_invoice": invoice.id,
        })
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("provider", "commune"), pk=pk)
    products = invoice.products.select_related(
        "fund", "subclass", "subclass__asset_class", "subclass__inventory_class",
    ).all()
    documents = [
        {"name": link.document.document_name, "url": document_url(link.document)}
        for link in invoice.document_links.filter(is_active=True).select_related("document")
    ]
    return render(request, "inventario/modal_invoice_detail.html", {
        "invoice": invoice,
        "products": products,
        "documents": documents,
        "can_edit": can_edit_inventory(request),
        "can_cancel": is_inventory_superadmin(request),
    })


@login_required
@transaction.atomic
def invoice_document_upload(request, pk):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)
    try:
        invoice = get_object_or_404(Invoice, pk=pk)
        files = request.FILES.getlist("invoice_documents")
        if not files:
            raise ValueError("Debe seleccionar al menos un documento.")
        for uploaded in files:
            document = save_uploaded_document(request, uploaded, "Inventario - Factura", f"facturas/{invoice.id}")
            audit_save(InvoiceDocument(invoice=invoice, document=document), request.user)
        return JsonResponse({"status": "success", "message": "Documento(s) agregado(s) correctamente."})
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
@transaction.atomic
def invoice_cancel(request, pk):
    if not is_inventory_superadmin(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos para anular facturas."}, status=403)
    try:
        invoice = Invoice.objects.select_for_update().get(pk=pk)
        if invoice.status != Invoice.STATUS_CURRENT or not invoice.is_active:
            raise ValueError("La factura ya se encuentra deshabilitada.")

        invoice.status = Invoice.STATUS_DIGIT_ERROR
        invoice.is_active = False
        audit_save(invoice, request.user)
        invoice.products.update(status=Product.STATUS_INACTIVE, is_active=False)
        return JsonResponse({"status": "success", "message": "La factura fue marcada como error de digitación."})
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})
