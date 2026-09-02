from django.urls import path

from .views import (
    loan_actions,
    loan_extraordinary,
    loan_payment_manager,
    loan_portfolio,
    loan_reports,
)


app_name = "loan"


urlpatterns = [
    # ============================================================
    # CARTERA DE PRESTAMOS
    path("", loan_portfolio.loan_portfolio, name="portfolio"),
    path("datatable/", loan_portfolio.loan_portfolio_datatable, name="portfolio_datatable"),
    path("<int:loan_id>/detail/", loan_portfolio.loan_detail, name="detail"),

    # ============================================================
    # ACCIONES DEL MODAL
    path("<int:loan_id>/action/<str:action>/modal/", loan_actions.loan_action_modal, name="action_modal"),
    path("<int:loan_id>/action/<str:action>/", loan_actions.loan_action_post, name="action_post"),
    path("<int:loan_id>/guarantors/search/", loan_actions.guarantor_search, name="guarantor_search"),
    path(
        "<int:loan_id>/payments/<int:payment_id>/detail/",
        loan_actions.payment_detail,
        name="payment_detail",
    ),

    # ============================================================
    # PRESTAMO EXTRAORDINARIO
    path("extraordinary/", loan_extraordinary.loan_extraordinary, name="extraordinary"),
    path(
        "extraordinary/person-search/",
        loan_extraordinary.extraordinary_person_search,
        name="extraordinary_person_search",
    ),
    path(
        "extraordinary/concepts/",
        loan_extraordinary.extraordinary_concepts,
        name="extraordinary_concepts",
    ),
    path(
        "extraordinary/simulate/",
        loan_extraordinary.extraordinary_simulate,
        name="extraordinary_simulate",
    ),
    path(
        "extraordinary/create/",
        loan_extraordinary.extraordinary_create,
        name="extraordinary_create",
    ),

    # ============================================================
    # INFORMES
    path("reports/", loan_reports.loan_reports, name="reports"),

    # ============================================================
    # GESTOR DE PAGOS
    path(
        "payments/", 
        loan_payment_manager.loan_payment_manager, 
        name="payment_manager"
    ),
    path(
        "payments/datatable/",
        loan_payment_manager.payment_manager_datatable,
        name="payment_manager_datatable",
    ),
    path(
        "payments/<int:payment_id>/action/",
        loan_payment_manager.payment_action,
        name="payment_action",
    ),
    path(
        "payments/<int:payment_id>/reversal/info/",
        loan_payment_manager.payment_reversal_info,
        name="payment_reversal_info",
    ),
    path(
        "payments/<int:payment_id>/reversal/request/",
        loan_payment_manager.payment_reversal_request,
        name="payment_reversal_request",
    ),
    path(
        "payments/<int:payment_id>/reversal/decision/",
        loan_payment_manager.payment_reversal_decision,
        name="payment_reversal_decision",
    ),
]
