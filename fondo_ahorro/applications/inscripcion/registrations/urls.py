from django.urls import path

from . import views


app_name = "registrations"


urlpatterns = [
    path("", views.registration_list, name="list"),

    path("datatable/", views.registration_datatable, name="datatable"),
    path("employee/search/", views.search_employee, name="search_employee"),
    path("locations/communes/<int:region_id>/",views.communes_by_region,name="communes_by_region",),
    path("create/", views.create_registration, name="create"),
    path("<int:registration_id>/detail/",views.registration_detail,name="detail",),
    path("<int:registration_id>/status/",views.update_registration_status,name="update_status",),
    path("<int:registration_id>/documents/add/",views.add_registration_document,name="add_document",),
    path("<int:registration_id>/documents/<int:document_relation_id>/status/",views.update_document_status,name="update_document_status",),
]