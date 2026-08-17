import json
import uuid

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import (
    Person,
    Document,
    DocumentType,
    Observation,
    Request,
    RequestType,
    RequestStatus,
    Employee,
    Partner,
    PartnerReentry,
)

from .models import (
    Registration,
    RegistrationType,
    RegistrationDocument,
    RegistrationDocumentStatus,
    RegistrationObservation,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

MAX_FILE_SIZE = 10 * 1024 * 1024

# Número máximo de REINGRESOS después del ingreso inicial.
#
# Ejemplo:
#   1 = primer ingreso + máximo 1 reincorporación.
#   2 = primer ingreso + máximo 2 reincorporaciones.
#
MAX_PARTNER_REENTRIES = 1

REGISTRATION_TYPE_INITIAL = "Registration"
REGISTRATION_TYPE_REENTRY = "Re-registration"

REQUEST_TYPE_REGISTRATION = "Registration"

REQUEST_STATUS_PENDING = "Pending"
REQUEST_STATUS_APPROVED = "Approved"
REQUEST_STATUS_REJECTED = "Rejected"

DOCUMENT_STATUS_PENDING = "Pending"


# ============================================================
# FUNCIONES AUXILIARES
def _person_full_name(person):
    parts = [person.first_name, person.second_name, person.last_name_1, person.last_name_2]
    return " ".join(str(value).strip() for value in parts if value)


def _person_rut(person):
    return f"{person.rut}-{person.dv}"


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def _format_datetime(value):
    if not value:
        return ""

    if timezone.is_aware(value):
        value = timezone.localtime(value)

    return value.strftime("%d-%m-%Y %H:%M")


def _registration_type_label(value):
    value = str(value or "").strip().lower()

    if value == REGISTRATION_TYPE_INITIAL.lower():
        return "Inscripción"

    if value == REGISTRATION_TYPE_REENTRY.lower():
        return "Reingreso"

    return value or "-"


def _find_employee_by_code(code):
    employee = (
        Employee.objects
        .select_related("person", "grade")
        .filter(code=str(code).strip())
        .first()
    )

    if not employee:
        return None

    return {
        "person": employee.person,
        "code": employee.code,
        "grade": employee.grade.name if employee.grade else "",
    }


def _employee_codes(person_ids):
    if not person_ids:
        return {}

    return {
        employee["person_id"]: employee["code"]
        for employee in Employee.objects
        .filter(person_id__in=person_ids)
        .values("person_id", "code")
    }


def _person_ids_by_employee_code(search):
    if not search:
        return []

    return list(
        Employee.objects
        .filter(code__icontains=search)
        .values_list("person_id", flat=True)
    )


def _get_core_request(registration_id):
    return (
        Request.objects
        .select_related("request_type", "status")
        .filter(
            request_id=registration_id,
            request_type__type__iexact=REQUEST_TYPE_REGISTRATION,
        )
        .order_by("-id")
        .first()
    )


def _get_partner_situation(person):
    """
    Determina si el funcionario puede generar una solicitud.

    CASO 1:
        No existe Partner.
        -> Inscripción inicial.

    CASO 2:
        Existe Partner y state = 1.
        -> Ya es socio activo.
        -> No puede generar otra solicitud.

    CASO 3:
        Existe Partner y state = 0.
        -> Puede corresponder a reingreso.

    PartnerReentry registra todos los ingresos del socio,
    incluido el ingreso inicial.

    Por lo tanto:

        reingresos utilizados = total PartnerReentry - 1
    """

    partner = Partner.objects.filter(person=person).first()

    # ========================================================
    # NUNCA HA SIDO SOCIO
    # ========================================================

    if not partner:
        return {
            "allowed": True,
            "partner": None,
            "type": REGISTRATION_TYPE_INITIAL,
            "member_status": "No socio",
            "is_reentry": False,
            "reentries_used": 0,
        }

    # ========================================================
    # SOCIO ACTIVO
    if partner.state == 1:
        return {
            "allowed": False,
            "partner": partner,
            "message": "El funcionario ya es socio activo.",
        }

    # ========================================================
    # SOCIO INACTIVO
    total_entries = PartnerReentry.objects.filter(partner=partner).count()
    reentries_used = max(total_entries - 1, 0)

    if reentries_used >= MAX_PARTNER_REENTRIES:
        plural = "s" if MAX_PARTNER_REENTRIES != 1 else ""

        return {
            "allowed": False,
            "partner": partner,
            "message": (
                f"El funcionario ya utilizó el máximo de {MAX_PARTNER_REENTRIES} "
                f"reingreso{plural} permitido{plural}."
            ),
        }

    return {
        "allowed": True,
        "partner": partner,
        "type": REGISTRATION_TYPE_REENTRY,
        "member_status": "Socio inactivo",
        "is_reentry": True,
        "reentries_used": reentries_used,
    }


def _get_registration_type(situation):
    registration_type, _ = RegistrationType.objects.get_or_create(
        type=situation["type"],
        defaults={"state": 1},
    )

    if registration_type.state != 1:
        registration_type.state = 1
        registration_type.save(update_fields=["state"])

    return registration_type


def _validate_pdf(uploaded_file):
    if not uploaded_file:
        return

    extension = Path(uploaded_file.name).suffix.lower()

    if extension != ".pdf":
        raise ValueError(f'El archivo "{uploaded_file.name}" debe estar en formato PDF.')

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError(f'El archivo "{uploaded_file.name}" supera el máximo de 10 MB.')


def _save_document(*, uploaded_file, registration, document_type_name, document_status, request):
    _validate_pdf(uploaded_file)

    document_type, _ = DocumentType.objects.get_or_create(
        type=document_type_name,
        defaults={"state": 1},
    )

    internal_name = uuid.uuid4().hex
    extension = Path(uploaded_file.name).suffix.lower()

    relative_path = f"registrations/{registration.id}/{internal_name}{extension}"

    saved_path = default_storage.save(relative_path, uploaded_file)

    document = Document.objects.create(
        user=request.user,
        type_document=document_type,
        ip=_get_client_ip(request),
        size=uploaded_file.size,
        document_name=uploaded_file.name,
        internal_name=internal_name,
        file_type=uploaded_file.content_type or "application/pdf",
        route=saved_path,
    )

    RegistrationDocument.objects.create(
        registration=registration,
        document=document,
        status=document_status,
    )

    return document, saved_path


def _create_observation(request, registration, comment):
    observation = Observation.objects.create(
        comment=comment,
        user=request.user,
        date=timezone.localdate(),
        time=timezone.localtime().time(),
        ip=_get_client_ip(request),
    )

    RegistrationObservation.objects.create(
        registration=registration,
        observation=observation,
        state=1,
    )

    return observation


def _process_approved_partner_registration(registration, core_request, user):
    """
    Procesa el ingreso como socio solamente cuando una solicitud
    es APROBADA.

    INSCRIPCIÓN INICIAL:
        Partner no existe.
        -> Crear Partner state = 1.
        -> Crear PartnerReentry state = 1.

    REINGRESO:
        Partner existe con state = 0.
        -> Validar cantidad máxima de reingresos.
        -> Desactivar cualquier PartnerReentry anterior activo.
        -> Reactivar Partner.
        -> Crear nuevo PartnerReentry state = 1.
    """

    existing_entry = PartnerReentry.objects.filter(request=core_request).first()

    # Evita procesar dos veces la misma solicitud.
    if existing_entry:
        return existing_entry.partner

    registration_type = str(registration.registration_type.type or "").strip()
    is_reentry = registration_type.lower() == REGISTRATION_TYPE_REENTRY.lower()

    partner = (
        Partner.objects
        .select_for_update()
        .filter(person=registration.person)
        .first()
    )

    now = timezone.now()
    today = timezone.localdate()

    # ========================================================
    # INSCRIPCIÓN INICIAL
    if not is_reentry:

        if partner:
            if partner.state == 1:
                raise ValueError("El funcionario ya se encuentra registrado como socio activo.")

            raise ValueError(
                "El funcionario ya posee un registro de socio. "
                "La solicitud debería corresponder a un reingreso."
            )

        partner = Partner.objects.create(
            person=registration.person,
            state=1,
            created_at=now,
            updated_at=now,
            user_create=user,
            user_update=user,
        )

    # ========================================================
    # REINGRESO
    else:

        if not partner:
            raise ValueError("No existe un registro de socio para realizar el reingreso.")

        if partner.state == 1:
            raise ValueError("El funcionario ya se encuentra como socio activo.")

        total_entries = PartnerReentry.objects.filter(partner=partner).count()
        reentries_used = max(total_entries - 1, 0)

        if reentries_used >= MAX_PARTNER_REENTRIES:
            raise ValueError("El socio ya utilizó la cantidad máxima de reingresos permitidos.")

        # ----------------------------------------------------
        # DESACTIVAR INGRESO ANTERIOR
        PartnerReentry.objects.filter(
            partner=partner,
            state=1,
        ).update(
            state=0,
            updated_at=now,
            user_update=user,
        )

        # ----------------------------------------------------
        # REACTIVAR SOCIO
        partner.state = 1
        partner.updated_at = now
        partner.user_update = user

        partner.save(
            update_fields=[
                "state",
                "updated_at",
                "user_update",
            ]
        )

    # ========================================================
    # REGISTRAR NUEVO PERÍODO COMO SOCIO
    PartnerReentry.objects.create(
        partner=partner,
        request=core_request,
        entry_date=today,
        resignation_date=None,
        state=1,
        created_at=now,
        updated_at=now,
        user_create=user,
        user_update=user,
    )

    return partner


# ============================================================
# VISTA PRINCIPAL
@login_required
def registration_list(request):
    return render(request, "inscripcion/registration_list.html")


# ============================================================
# DATATABLE
@login_required
@require_GET
def registration_datatable(request):
    try:
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
        search = (request.GET.get("search[value]", "") or "").strip()

        # ====================================================
        # REQUEST ASOCIADO
        request_qs = (
            Request.objects
            .filter(
                request_id=OuterRef("pk"),
                request_type__type__iexact=REQUEST_TYPE_REGISTRATION,
            )
            .order_by("-id")
        )

        queryset = (
            Registration.objects
            .select_related(
                "person",
                "registration_type",
                "user",
            )
            .annotate(
                request_date=Subquery(request_qs.values("date")[:1]),
                request_status=Subquery(request_qs.values("status__status_type")[:1]),
            )
            .order_by("-id")
        )

        records_total = queryset.count()

        # ====================================================
        # BUSCADOR
        if search:
            search_filter = (
                Q(person__first_name__icontains=search)
                | Q(person__second_name__icontains=search)
                | Q(person__last_name_1__icontains=search)
                | Q(person__last_name_2__icontains=search)
                | Q(registration_type__type__icontains=search)
            )

            if search.isdigit():
                search_filter |= Q(person__rut=int(search))
                search_filter |= Q(contributes_a2=int(search))

            employee_person_ids = _person_ids_by_employee_code(search)

            if employee_person_ids:
                search_filter |= Q(person_id__in=employee_person_ids)

            queryset = queryset.filter(search_filter)

        records_filtered = queryset.count()

        # ====================================================
        # PAGINACIÓN
        registrations = list(queryset[start:start + length])

        person_ids = [
            registration.person_id
            for registration in registrations
            if registration.person_id
        ]

        employee_codes = _employee_codes(person_ids)

        # ====================================================
        # RESPUESTA
        data = []

        for registration in registrations:
            person = registration.person

            data.append({
                "id": registration.id,

                "employee_code": employee_codes.get(
                    registration.person_id,
                    "",
                ),

                "rut": (
                    _person_rut(person)
                    if person
                    else ""
                ),

                "employee_name": (
                    _person_full_name(person)
                    if person
                    else ""
                ),

                "registration_type": _registration_type_label(
                    registration.registration_type.type
                    if registration.registration_type
                    else ""
                ),

                # IMPORTANTE:
                # Se devuelve como número.
                # El JavaScript lo formatea como moneda chilena.
                "contributes_a2": registration.contributes_a2 or 0,

                "date": _format_datetime(registration.request_date),

                "status": registration.request_status or "",
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        })

    except Exception as error:
        return JsonResponse({
            "draw": int(request.GET.get("draw", 1)),
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
            "error": str(error),
        }, status=500)


# ============================================================
# BUSCAR FUNCIONARIO
@login_required
@require_POST
def search_employee(request):
    try:
        body = json.loads(request.body or "{}")
        code = str(body.get("code", "")).strip()

        if not code:
            return JsonResponse({
                "status": "error",
                "message": "Debe ingresar el código del funcionario.",
            }, status=400)

        employee = _find_employee_by_code(code)

        if not employee:
            return JsonResponse({
                "status": "error",
                "message": "No se encontró un funcionario con ese código.",
            }, status=404)

        person = employee["person"]

        # ====================================================
        # EVITAR OTRA SOLICITUD PENDIENTE
        registration_ids = (
            Registration.objects
            .filter(person=person)
            .values_list("id", flat=True)
        )

        has_pending = (
            Request.objects
            .filter(
                request_id__in=registration_ids,
                request_type__type__iexact=REQUEST_TYPE_REGISTRATION,
                status__status_type__iexact=REQUEST_STATUS_PENDING,
            )
            .exists()
        )

        if has_pending:
            return JsonResponse({
                "status": "error",
                "message": "El funcionario ya posee una solicitud de inscripción pendiente.",
            }, status=400)

        # ====================================================
        # DETERMINAR INSCRIPCIÓN / REINGRESO
        situation = _get_partner_situation(person)

        if not situation["allowed"]:
            return JsonResponse({
                "status": "error",
                "message": situation["message"],
            }, status=400)

        registration_type = _get_registration_type(situation)

        return JsonResponse({
            "status": "ok",

            "employee": {
                "person_id": person.id,
                "code": employee["code"],
                "rut": _person_rut(person),
                "name": _person_full_name(person),
                "grade": employee["grade"],
                "member_status": situation["member_status"],
            },

            "registration_type": {
                "id": registration_type.id,
                "type": registration_type.type,
                "display_name": _registration_type_label(registration_type.type),
                "is_reentry": situation["is_reentry"],
            },

            "reentries": {
                "used": situation["reentries_used"],
                "maximum": MAX_PARTNER_REENTRIES,
            },
        })

    except Exception as error:
        return JsonResponse({
            "status": "error",
            "message": str(error),
        }, status=500)


# ============================================================
# CREAR SOLICITUD
@login_required
@require_POST
def create_registration(request):
    saved_files = []

    try:
        # ====================================================
        # DATOS PRINCIPALES
        try:
            person_id = int(request.POST.get("person_id", 0))
        except (TypeError, ValueError):
            person_id = 0

        try:
            registration_type_id = int(request.POST.get("registration_type", 0))
        except (TypeError, ValueError):
            registration_type_id = 0

        # ====================================================
        # APORTE A2
        #
        # Puede ser:
        #   0
        #   1000
        #   25000
        #
        # No puede ser negativo ni texto.

        contributes_a2_raw = request.POST.get("contributes_a2", "0")

        try:
            contributes_a2 = int(contributes_a2_raw)
        except (TypeError, ValueError):
            raise ValueError("El aporte A2 debe ser un valor numérico.")

        if contributes_a2 < 0:
            raise ValueError("El aporte A2 no puede ser negativo.")

        # ====================================================
        # VALIDACIONES
        if person_id <= 0:
            raise ValueError("Debe seleccionar un funcionario.")

        if registration_type_id <= 0:
            raise ValueError("No se pudo determinar el tipo de solicitud.")

        person = Person.objects.filter(pk=person_id).first()

        if not person:
            raise ValueError("La persona seleccionada no existe.")

        employee_exists = Employee.objects.filter(person=person).exists()

        if not employee_exists:
            raise ValueError("La persona seleccionada no corresponde a un funcionario.")

        # ====================================================
        # VOLVER A VALIDAR ESTADO DEL SOCIO EN BACKEND
        situation = _get_partner_situation(person)

        if not situation["allowed"]:
            raise ValueError(situation["message"])

        expected_registration_type = _get_registration_type(situation)

        if registration_type_id != expected_registration_type.id:
            raise ValueError(
                "El tipo de solicitud no corresponde al estado actual del funcionario."
            )

        registration_ids = (
            Registration.objects
            .filter(person=person)
            .values_list("id", flat=True)
        )

        has_pending = (
            Request.objects
            .filter(
                request_id__in=registration_ids,
                request_type__type__iexact=REQUEST_TYPE_REGISTRATION,
                status__status_type__iexact=REQUEST_STATUS_PENDING,
            )
            .exists()
        )

        if has_pending:
            raise ValueError(
                "El funcionario ya posee una solicitud de inscripción pendiente."
            )

        # ====================================================
        # DOCUMENTOS
        physical_request = request.FILES.get("physical_request_document")
        identification_document = request.FILES.get("identification_document")
        other_documents = request.FILES.getlist("other_documents")

        if not physical_request:
            raise ValueError("Debe adjuntar la solicitud firmada.")

        if not identification_document:
            raise ValueError("Debe adjuntar el documento de identificación.")

        _validate_pdf(physical_request)
        _validate_pdf(identification_document)

        for uploaded_file in other_documents:
            _validate_pdf(uploaded_file)

        # ====================================================
        # TIPOS Y ESTADOS
        request_type, _ = RequestType.objects.get_or_create(
            type=REQUEST_TYPE_REGISTRATION,
            defaults={"state": 1},
        )

        if request_type.state != 1:
            request_type.state = 1
            request_type.save(update_fields=["state"])

        pending_status, _ = RequestStatus.objects.get_or_create(
            status_type=REQUEST_STATUS_PENDING,
            defaults={"state": 1},
        )

        if pending_status.state != 1:
            pending_status.state = 1
            pending_status.save(update_fields=["state"])

        document_pending_status, _ = RegistrationDocumentStatus.objects.get_or_create(
            status_type=DOCUMENT_STATUS_PENDING,
            defaults={"state": 1},
        )

        if document_pending_status.state != 1:
            document_pending_status.state = 1
            document_pending_status.save(update_fields=["state"])

        # ====================================================
        # TRANSACCIÓN
        with transaction.atomic():

            registration = Registration.objects.create(
                person=person,
                registration_type=expected_registration_type,
                contributes_a2=contributes_a2,
                user=request.user,
                user_ip=_get_client_ip(request),
            )

            core_request = Request.objects.create(
                request_id=registration.id,
                request_type=request_type,
                date=timezone.now(),
                status=pending_status,
            )

            # =================================================
            # SOLICITUD FIRMADA
            _, path = _save_document(
                uploaded_file=physical_request,
                registration=registration,
                document_type_name="Physical Registration Request",
                document_status=document_pending_status,
                request=request,
            )

            saved_files.append(path)

            # =================================================
            # DOCUMENTO DE IDENTIFICACIÓN
            _, path = _save_document(
                uploaded_file=identification_document,
                registration=registration,
                document_type_name="Identification Document",
                document_status=document_pending_status,
                request=request,
            )

            saved_files.append(path)

            # =================================================
            # OTROS DOCUMENTOS
            for other_file in other_documents:
                _, path = _save_document(
                    uploaded_file=other_file,
                    registration=registration,
                    document_type_name="Other Document",
                    document_status=document_pending_status,
                    request=request,
                )

                saved_files.append(path)

            # =================================================
            # OBSERVACIÓN INICIAL
            action_name = (
                "reingreso"
                if situation["is_reentry"]
                else "inscripción"
            )

            _create_observation(
                request,
                registration,
                f"Solicitud de {action_name} creada.",
            )

        return JsonResponse({
            "status": "ok",
            "message": "Solicitud creada correctamente.",
            "registration_id": registration.id,
            "request_id": core_request.id,
        })

    except ValueError as error:
        for path in saved_files:
            if default_storage.exists(path):
                default_storage.delete(path)

        return JsonResponse({
            "status": "error",
            "message": str(error),
        }, status=400)

    except Exception as error:
        for path in saved_files:
            if default_storage.exists(path):
                default_storage.delete(path)

        return JsonResponse({
            "status": "error",
            "message": f"Error al crear la solicitud: {error}",
        }, status=500)


# ============================================================
# DETALLE SOLICITUD
@login_required
@require_GET
def registration_detail(request, registration_id):
    registration = (
        Registration.objects
        .select_related(
            "person",
            "registration_type",
            "user",
        )
        .filter(pk=registration_id)
        .first()
    )

    if not registration:
        return JsonResponse({
            "status": "error",
            "message": "No se encontró la solicitud.",
        }, status=404)

    person = registration.person
    core_request = _get_core_request(registration.id)

    # ========================================================
    # DOCUMENTOS
    documents = []

    for relation in (
        registration.documents
        .select_related(
            "document",
            "document__type_document",
            "status",
        )
        .all()
    ):
        document = relation.document
        file_url = ""

        if document.route:
            try:
                file_url = default_storage.url(document.route)
            except Exception:
                file_url = document.route

        documents.append({
            "id": document.id,

            "name": document.document_name,

            "type": (
                document.type_document.type
                if document.type_document
                else ""
            ),

            "status": (
                relation.status.status_type
                if relation.status
                else ""
            ),

            "date": _format_datetime(document.creation_date),

            "url": file_url,
        })

    # ========================================================
    # OBSERVACIONES
    observations = []

    for relation in (
        registration.observations
        .select_related(
            "observation",
            "observation__user",
        )
        .filter(state=1)
        .order_by(
            "-observation__date",
            "-observation__time",
        )
    ):
        observation = relation.observation

        observations.append({
            "comment": observation.comment or "",

            "date": (
                observation.date.strftime("%d-%m-%Y")
                if observation.date
                else ""
            ),

            "time": (
                observation.time.strftime("%H:%M")
                if observation.time
                else ""
            ),

            "user": (
                observation.user.username
                if observation.user
                else ""
            ),
        })

    request_status = (
        core_request.status.status_type
        if core_request and core_request.status
        else ""
    )

    employee_code = ""

    if person:
        employee_code = (
            Employee.objects
            .filter(person=person)
            .values_list("code", flat=True)
            .first()
            or ""
        )

    return JsonResponse({
        "status": "ok",

        "registration": {
            "id": registration.id,

            "employee_code": employee_code,

            "rut": (
                _person_rut(person)
                if person
                else ""
            ),

            "name": (
                _person_full_name(person)
                if person
                else ""
            ),

            "type": _registration_type_label(
                registration.registration_type.type
                if registration.registration_type
                else ""
            ),

            "contributes_a2": registration.contributes_a2 or 0,

            "status": request_status,

            "date": _format_datetime(
                core_request.date
                if core_request
                else None
            ),
        },

        "documents": documents,

        "observations": observations,

        "management": {
            "can_change_status": (
                request_status.lower()
                == REQUEST_STATUS_PENDING.lower()
            ),
        },
    })


# ============================================================
# CAMBIAR ESTADO DE LA SOLICITUD
@login_required
@require_POST
def update_registration_status(request, registration_id):
    try:
        body = json.loads(request.body or "{}")
        new_status = str(body.get("status", "")).strip()

        allowed_statuses = {
            REQUEST_STATUS_APPROVED.lower(): REQUEST_STATUS_APPROVED,
            REQUEST_STATUS_REJECTED.lower(): REQUEST_STATUS_REJECTED,
        }

        normalized_status = allowed_statuses.get(new_status.lower())

        if not normalized_status:
            return JsonResponse({
                "status": "error",
                "message": "El estado seleccionado no es válido.",
            }, status=400)

        with transaction.atomic():

            # =================================================
            # SOLICITUD
            registration = (
                Registration.objects
                .select_for_update()
                .select_related(
                    "person",
                    "registration_type",
                )
                .filter(pk=registration_id)
                .first()
            )

            if not registration:
                raise ValueError("No se encontró la solicitud.")

            # =================================================
            # REQUEST
            core_request = (
                Request.objects
                .select_for_update()
                .select_related(
                    "status",
                    "request_type",
                )
                .filter(
                    request_id=registration.id,
                    request_type__type__iexact=REQUEST_TYPE_REGISTRATION,
                )
                .order_by("-id")
                .first()
            )

            if not core_request:
                raise ValueError("La solicitud no posee un Request asociado.")

            current_status = str(
                core_request.status.status_type
                if core_request.status
                else ""
            ).strip()

            # =================================================
            # ESTADOS TERMINALES
            if current_status.lower() in (
                REQUEST_STATUS_APPROVED.lower(),
                REQUEST_STATUS_REJECTED.lower(),
            ):
                raise ValueError(
                    "La solicitud ya se encuentra en un estado final."
                )

            if current_status.lower() != REQUEST_STATUS_PENDING.lower():
                raise ValueError(
                    "Solo se pueden gestionar solicitudes pendientes."
                )

            # =================================================
            # APROBACIÓN
            if normalized_status == REQUEST_STATUS_APPROVED:
                _process_approved_partner_registration(
                    registration=registration,
                    core_request=core_request,
                    user=request.user,
                )

            # =================================================
            # ACTUALIZAR ESTADO REQUEST
            status_object, _ = RequestStatus.objects.get_or_create(
                status_type=normalized_status,
                defaults={"state": 1},
            )

            if status_object.state != 1:
                status_object.state = 1
                status_object.save(update_fields=["state"])

            core_request.status = status_object
            core_request.save(update_fields=["status"])

            # =================================================
            # OBSERVACIÓN
            status_label = (
                "aprobada"
                if normalized_status == REQUEST_STATUS_APPROVED
                else "rechazada"
            )

            _create_observation(
                request,
                registration,
                f"Solicitud {status_label}.",
            )

        return JsonResponse({
            "status": "ok",
            "message": f"Solicitud {status_label} correctamente.",
        })

    except ValueError as error:
        return JsonResponse({
            "status": "error",
            "message": str(error),
        }, status=400)

    except Exception as error:
        return JsonResponse({
            "status": "error",
            "message": f"Error al actualizar la solicitud: {error}",
        }, status=500)