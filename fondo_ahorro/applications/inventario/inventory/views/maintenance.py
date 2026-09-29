from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render

from ..models import AssetClass, InventoryClass, Office, Subclass
from ..utils import accounting_account, accounting_accounts, audit_save, can_edit_inventory


@login_required
def maintenance_modal(request):
    if not can_edit_inventory(request):
        return render(request, "inventario/modal_maintenance.html", {"permission_denied": True})

    subclasses = []
    queryset = Subclass.objects.select_related("inventory_class", "asset_class").order_by(
        "-is_active", "asset_class__name", "inventory_class__name", "name",
    )
    for subclass in queryset:
        account = accounting_account(subclass.accounting_account_id)
        subclasses.append({
            "obj": subclass,
            "account_name": account["name"],
            "account_number": account["number"],
        })

    return render(request, "inventario/modal_maintenance.html", {
        "asset_classes": AssetClass.objects.all().order_by("-is_active", "name"),
        "classes": InventoryClass.objects.all().order_by("-is_active", "name"),
        "subclasses": subclasses,
        "accounts": accounting_accounts(),
        "offices": Office.objects.all().order_by("-is_active", "name"),
    })


@login_required
@transaction.atomic
def maintenance_save(request):
    if not can_edit_inventory(request):
        return JsonResponse({"status": "error", "message": "No tiene permisos."}, status=403)
    try:
        kind = request.POST.get("type", "")
        pk = int(request.POST.get("id", 0) or 0)
        name = (request.POST.get("name", "") or "").strip()
        active = request.POST.get("is_active", "1") == "1"
        if not name:
            raise ValueError("Debe ingresar el nombre.")

        if kind == "asset_class":
            obj = AssetClass.objects.filter(pk=pk).first() or AssetClass()
            obj.name = name
        elif kind == "class":
            obj = InventoryClass.objects.filter(pk=pk).first() or InventoryClass()
            obj.name = name
        elif kind == "office":
            obj = Office.objects.filter(pk=pk).first() or Office()
            obj.name = name
        elif kind == "subclass":
            obj = Subclass.objects.filter(pk=pk).first() or Subclass()
            obj.name = name
            obj.useful_life_years = int(request.POST.get("useful_life_years", 0) or 0)
            obj.inventory_class_id = int(request.POST.get("inventory_class", 0) or 0)
            obj.asset_class_id = int(request.POST.get("asset_class", 0) or 0)
            obj.accounting_account_id = int(request.POST.get("accounting_account", 0) or 0) or None
            if obj.useful_life_years <= 0 or not obj.inventory_class_id or not obj.asset_class_id:
                raise ValueError("Complete vida útil, clase y clase de activo.")
        else:
            raise ValueError("Tipo de mantenedor no válido.")

        obj.is_active = active
        audit_save(obj, request.user)
        return JsonResponse({"status": "success", "message": "Registro guardado correctamente."})
    except Exception as exc:
        transaction.set_rollback(True)
        return JsonResponse({"status": "error", "message": str(exc)})


@login_required
def initial_load(request):
    return JsonResponse({
        "status": "error",
        "message": (
            "La carga inicial por Excel queda pendiente porque el módulo PHP entregado referencia cargaInicial.php, "
            "pero ese archivo no fue incluido en las fuentes."
        ),
    }, status=501)
