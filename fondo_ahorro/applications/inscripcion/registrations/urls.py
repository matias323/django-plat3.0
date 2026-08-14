from django.urls import path

from . import views


app_name = "registrations"


urlpatterns = [
    path("", views.registration_list, name="list"),
    path("datatable/", views.registration_datatable, name="datatable"),

    path("employee/search/", views.search_employee, name="search_employee"),

    path("create/", views.create_registration, name="create"),

    path("<int:registration_id>/detail/", views.registration_detail, name="detail"),
    path("<int:registration_id>/status/", views.update_registration_status, name="update_status"),
]