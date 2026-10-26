from django.urls import path

from . import views


app_name = "loan_requests"


urlpatterns = [

    # ============================================================
    # LISTADO
    # ============================================================
    path(
        "",
        views.request_loan_list,
        name="list",
    ),

    path(
        "datatable/",
        views.request_loan_datatable,
        name="datatable",
    ),


    # ============================================================
    # CREAR
    # ============================================================
    path(
        "new/",
        views.request_loan_create,
        name="create",
    ),


    # ============================================================
    # BUSQUEDA FUNCIONARIO
    # ============================================================
    path(
        "employees/search/",
        views.employee_search,
        name="employee_search",
    ),


    # ============================================================
    # CONCEPTOS
    # ============================================================
    path(
        "concepts/",
        views.request_loan_concepts,
        name="concepts",
    ),


    # ============================================================
    # DETALLE MODAL
    # ============================================================
    path(
        "<int:pk>/detail-modal/",
        views.request_loan_detail_modal,
        name="detail_modal",
    ),


    # ============================================================
    # DETALLE COMPLETO
    # ============================================================
    path(
        "<int:pk>/",
        views.request_loan_detail,
        name="detail",
    ),


    # ============================================================
    # DOCUMENTOS
    # ============================================================
    path(
        "<int:pk>/documents/<int:required_id>/upload/",
        views.request_loan_document_upload,
        name="document_upload",
    ),

    path(
        "<int:pk>/documents/<int:document_id>/view/",
        views.request_loan_document_view,
        name="document_view",
    ),

    path(
        "<int:pk>/documents/<int:document_id>/approve/",
        views.request_loan_document_approve,
        name="document_approve",
    ),

    path(
        "<int:pk>/documents/<int:document_id>/reject/",
        views.request_loan_document_reject,
        name="document_reject",
    ),


    # ============================================================
    # SOLICITUD
    # ============================================================
    path(
        "<int:pk>/approve/",
        views.request_loan_approve,
        name="approve",
    ),

    path(
        "<int:pk>/reject/",
        views.request_loan_reject,
        name="reject",
    ),

    path(
        "<int:pk>/observations/add/",
        views.request_loan_add_observation,
        name="add_observation",
    ),
]