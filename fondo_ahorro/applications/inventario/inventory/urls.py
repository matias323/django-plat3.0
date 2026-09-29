from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.inventory, name="index"),

    # Productos
    path("products/data/", views.products_data, name="products_data"),
    path("products/person/data/", views.person_products_data, name="person_products_data"),
    path("products/modal/", views.product_modal, name="product_modal"),
    path("products/save/", views.product_save, name="product_save"),

    # Buscadores
    path("search/people/", views.search_people, name="search_people"),
    path("search/subclasses/", views.search_subclasses, name="search_subclasses"),
    path("search/communes/", views.search_communes, name="search_communes"),

    # Facturas
    path("invoices/data/", views.invoices_data, name="invoices_data"),
    path("invoices/modal/", views.invoice_modal, name="invoice_modal"),
    path("invoices/provider/", views.provider_lookup, name="provider_lookup"),
    path("invoices/save/", views.invoice_save, name="invoice_save"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/documents/", views.invoice_document_upload, name="invoice_document_upload"),
    path("invoices/<int:pk>/cancel/", views.invoice_cancel, name="invoice_cancel"),

    # Actas de entrega
    path("delivery-records/data/", views.delivery_records_data, name="delivery_records_data"),
    path("delivery-records/modal/", views.delivery_record_modal, name="delivery_record_modal"),
    path("delivery-records/search/lenders/", views.search_lenders, name="search_lenders"),
    path("delivery-records/search/products/", views.search_outgoing_products, name="search_outgoing_products"),
    path("delivery-records/save/", views.delivery_record_save, name="delivery_record_save"),
    path("delivery-records/<int:pk>/", views.delivery_record_detail, name="delivery_record_detail"),
    path(
        "delivery-records/<int:pk>/documents/", views.delivery_record_document_upload,
        name="delivery_record_document_upload",
    ),
    path("delivery-records/<int:pk>/cancel/", views.delivery_record_cancel, name="delivery_record_cancel"),

    # Oficinas
    path("offices/list/", views.offices_list, name="offices_list"),
    path("offices/products/data/", views.office_products_data, name="office_products_data"),
    path("offices/people/data/", views.office_people_data, name="office_people_data"),
    path("offices/search/products/", views.search_office_products, name="search_office_products"),
    path("offices/search/people/", views.search_office_people, name="search_office_people"),
    path("offices/product/update/", views.office_product_update, name="office_product_update"),
    path("offices/person/update/", views.office_person_update, name="office_person_update"),
    path("offices/sync/", views.office_sync, name="office_sync"),
    path("offices/<int:pk>/export/", views.office_export, name="office_export"),

    # Mantenedor
    path("maintenance/", views.maintenance_modal, name="maintenance_modal"),
    path("maintenance/save/", views.maintenance_save, name="maintenance_save"),
    path("initial-load/", views.initial_load, name="initial_load"),
]
