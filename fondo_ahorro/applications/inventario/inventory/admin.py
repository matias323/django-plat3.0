from django.contrib import admin

from .models import (
    AssetClass, DeliveryRecord, DeliveryRecordDocument, DeliveryRecordProduct, DeliveryRecordStatus,
    DeliveryRecordType, Fund, InventoryClass, Invoice, InvoiceDocument, Office, OfficePerson, OfficeProduct,
    Product, ProductAssignment, ProductDocument, Subclass,
)


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(AssetClass)
class AssetClassAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(InventoryClass)
class InventoryClassAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Subclass)
class SubclassAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inventory_class", "asset_class", "useful_life_years", "is_active")
    search_fields = ("name", "inventory_class__name", "asset_class__name")
    list_filter = ("is_active", "asset_class", "inventory_class")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("role_number", "name", "brand", "fund", "subclass", "current_value", "status", "is_active")
    search_fields = ("name", "brand", "model", "role_number", "bcu_number", "sap_number", "serial_number")
    list_filter = ("status", "book", "fund", "subclass__asset_class")
    autocomplete_fields = ("invoice", "fund", "subclass")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "invoice_date", "provider_name", "net_amount", "vat_amount", "status", "is_active")
    search_fields = ("invoice_number", "provider_name", "provider__rut")
    list_filter = ("status", "is_active", "invoice_date")


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ("record_number", "record_date", "record_type", "status", "area", "lender", "is_active")
    search_fields = ("record_number", "area")
    list_filter = ("record_type", "status", "is_active", "record_date")


admin.site.register(ProductAssignment)
admin.site.register(ProductDocument)
admin.site.register(InvoiceDocument)
admin.site.register(OfficePerson)
admin.site.register(OfficeProduct)
admin.site.register(DeliveryRecordType)
admin.site.register(DeliveryRecordStatus)
admin.site.register(DeliveryRecordProduct)
admin.site.register(DeliveryRecordDocument)
