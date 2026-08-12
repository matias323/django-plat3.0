import json
import uuid

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.db.models import Q, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models.person import Person
from core.models.document import Document, DocumentType
from core.models.observation import Observation
from core.models.request import Request, RequestType, RequestStatus

from .models import (
    Registration,
    RegistrationType,
    RegistrationDocument,
    RegistrationDocumentStatus,
    RegistrationObservation,
)


# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _person_full_name(person):
    parts = [
        person.first_name,
        person.second_name,
        person.last_name_1,
        person.last_name_2,
    ]

    return " ".join(
        str(value).strip()
        for value in parts
        if value
    )


def _person_rut(person):
    return f"{person.rut}-{person.dv}"


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def _find_employee_by_code(code):
    """
    Busca el funcionario utilizando las tablas existentes
    funcionario y funcionario_grado.

    Cuando exista un modelo Django Employee/Funcionario,
    esta función se puede reemplazar por ORM.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                f.id_persona,
                f.codigo,
                COALESCE(fg.nombre, '')
            FROM funcionario f
            LEFT JOIN funcionario_grado fg
                ON fg.id = f.id_grado
            WHERE CAST(f.codigo AS TEXT) = %s
            LIMIT 1
            """,
            [str(code)],
        )

        row = cursor.fetchone()

    if not row:
        return None

    person_id, employee_code, grade = row

    person = Person.objects.filter(
        pk=person_id
    ).first()

    if not person:
        return None

    return {
        "person": person,
        "code": employee_code,
        "grade": grade,
    }


def _person_is_member(person_id):
    """
    Comprueba si la persona actualmente es socio activo.

    Utiliza temporalmente la tabla socio existente.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM socio
            WHERE id_persona = %s
              AND estado = 1
            LIMIT 1
            """,
            [person_id],
        )

        return cursor.fetchone() is not None


def _employee_codes(person_ids):
    """
    Devuelve:
        {
            person_id: codigo,
            ...
        }
    """

    if not person_ids:
        return {}

    placeholders = ", ".join(
        ["%s"] * len(person_ids)
    )

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id_persona, codigo
            FROM funcionario
            WHERE id_persona IN ({placeholders})
            """,
            list(person_ids),
        )

        rows = cursor.fetchall()

    return {
        row[0]: row[1]
        for row in rows
    }


def _person_ids_by_employee_code(search):
    if not search:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id_persona
            FROM funcionario
            WHERE CAST(codigo AS TEXT) ILIKE %s
            """,
            [f"%{search}%"],
        )

        rows = cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


def _validate_pdf(file):
    if not file:
        return

    extension = Path(file.name).suffix.lower()

    if extension != ".pdf":
        raise ValueError(
            f'El archivo "{file.name}" debe estar en formato PDF.'
        )

    if file.size > MAX_FILE_SIZE:
        raise ValueError(
            f'El archivo "{file.name}" supera el máximo de 10 MB.'
        )


def _save_document(
    *,
    uploaded_file,
    registration,
    document_type_name,
    document_status,
    request
):
    """
    Guarda:
        archivo físico
            ↓
        core_document
            ↓
        registration_document
    """

    _validate_pdf(uploaded_file)

    document_type, _ = DocumentType.objects.get_or_create(
        type=document_type_name,
        defaults={
            "state": 1
        }
    )

    internal_name = uuid.uuid4().hex

    extension = Path(
        uploaded_file.name
    ).suffix.lower()

    relative_path = (
        f"registrations/"
        f"{registration.id}/"
        f"{internal_name}{extension}"
    )

    saved_path = default_storage.save(
        relative_path,
        uploaded_file
    )

    document = Document.objects.create(
        user=request.user,
        type_document=document_type,
        ip=_get_client_ip(request),
        size=uploaded_file.size,
        document_name=uploaded_file.name,
        internal_name=internal_name,
        file_type=(
            uploaded_file.content_type
            or "application/pdf"
        ),
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


# ============================================================
# VISTA PRINCIPAL
# ============================================================

@login_required
def registration_list(request):
    return render(
        request,
        "inscripcion/registration_list.html",
    )


# ============================================================
# DATATABLE
# ============================================================

@login_required
@require_GET
def registration_datatable(request):
    try:
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
        search = (request.GET.get("search[value]","") or "").strip()

        # ====================================================
        # Request asociado a cada Registration
        # ====================================================

        request_qs = (Request.objects.filter(
            request_id=OuterRef("pk"),
            request_type__type__iexact="Registration",
        ).order_by("-id"))


        queryset = (
            Registration.objects
            .select_related(
                "person",
                "registration_type",
                "user",
            )
            .annotate(
                request_date=Subquery(
                    request_qs.values("date")[:1]
                ),
                request_status=Subquery(
                    request_qs.values(
                        "status__status_type"
                    )[:1]
                ),
            )
            .order_by("-id")
        )

        records_total = queryset.count()

        # ====================================================
        # BUSCADOR
        # ====================================================

        if search:
            search_filter = (
                Q(person__first_name__icontains=search)|
                Q(person__second_name__icontains=search)|
                Q(person__last_name_1__icontains=search)|
                Q(person__last_name_2__icontains=search)|
                Q(registration_type__type__icontains=search)
            )

            if search.isdigit():
                search_filter |= Q(
                    person__rut=int(search)
                )

            queryset = queryset.filter(
                search_filter
            )

        records_filtered = queryset.count()

        # ====================================================
        # PAGINACIÓN
        # ====================================================

        queryset = queryset[
            start:start + length
        ]

        # ====================================================
        # RESPUESTA
        # ====================================================

        data = []
        for registration in queryset:
            person = registration.person
            data.append({
                "id": registration.id,
                "employee_code": "",
                "rut": (_person_rut(person) if person else ""),
                "employee_name": (_person_full_name(person) if person else ""),
                "registration_type": (
                    registration.registration_type.type
                    if registration.registration_type
                    else ""
                ),
                "contributes_a2": ("Sí" if registration.contributes_a2 else "No"),
                "date": (registration.request_date.strftime("%d-%m-%Y %H:%M")
                    if registration.request_date
                    else ""
                ),
                "status": (registration.request_status or ""),
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        })


    except Exception as error:
        return JsonResponse(
            {
                "draw": int(request.GET.get("draw", 1)),
                "recordsTotal": 0,
                "recordsFiltered": 0,
                "data": [],
                "error": str(error),
            },
            status=500,
        )

# ============================================================
# BUSCAR FUNCIONARIO
# ============================================================

@login_required
@require_POST
def search_employee(request):

    try:
        body = json.loads(request.body or "{}")
        code = str(body.get("code", "")).strip()

        if not code:
            return JsonResponse(
                {
                    "status": "error",
                    "message": (
                        "Debe ingresar el código "
                        "del funcionario."
                    )
                },
                status=400,
            )

        employee = _find_employee_by_code(code)

        if not employee:
            return JsonResponse(
                {
                    "status": "error",
                    "message": (
                        "No se encontró un funcionario "
                        "con ese código."
                    )
                },
                status=404,
            )


        person = employee["person"]
        is_member = _person_is_member(person.id)

        # ----------------------------------------------------
        # Evitar dos solicitudes pendientes
        # ----------------------------------------------------

        registration_ids = (
            Registration.objects
            .filter(
                person=person
            )
            .values_list(
                "id",
                flat=True
            )
        )


        has_pending = (
            Request.objects
            .filter(
                request_id__in=registration_ids,
                request_type__type__iexact="Registration",
                status__status_type__iexact="Pending",
            )
            .exists()
        )

        if has_pending:
            return JsonResponse(
                {
                    "status": "error",
                    "message": (
                        "El funcionario ya posee "
                        "una solicitud de inscripción "
                        "pendiente."
                    )
                },
                status=400,
            )


        registration_type_name = (
            "Re-registration"
            if is_member
            else "Registration"
        )


        registration_type, _ = (
            RegistrationType.objects
            .get_or_create(
                type=registration_type_name,
                defaults={
                    "state": 1
                }
            )
        )


        return JsonResponse({
            "status": "ok",

            "employee": {
                "person_id": person.id,
                "code": employee["code"],
                "rut": _person_rut(person),
                "name": _person_full_name(person),
                "grade": employee["grade"],
                "is_member": is_member,
            },

            "registration_type": {
                "id": registration_type.id,
                "type": registration_type.type,
            }
        })


    except Exception as error:

        return JsonResponse(
            {
                "status": "error",
                "message": str(error),
            },
            status=500,
        )


# ============================================================
# CREAR SOLICITUD
# ============================================================

@login_required
@require_POST
def create_registration(request):

    saved_files = []

    try:

        person_id = int(
            request.POST.get(
                "person_id",
                0
            )
        )

        registration_type_id = int(
            request.POST.get(
                "registration_type",
                0
            )
        )

        contributes_a2 = (
            request.POST.get(
                "contributes_a2"
            )
        )


        if person_id <= 0:
            raise ValueError(
                "Debe seleccionar un funcionario."
            )


        if registration_type_id <= 0:
            raise ValueError(
                "No se pudo determinar "
                "el tipo de solicitud."
            )


        if contributes_a2 not in (
            "0",
            "1",
        ):
            raise ValueError(
                "Debe indicar si el funcionario "
                "aporta A2."
            )


        person = Person.objects.filter(
            pk=person_id
        ).first()


        if not person:
            raise ValueError(
                "La persona seleccionada "
                "no existe."
            )


        registration_type = (
            RegistrationType.objects
            .filter(
                pk=registration_type_id,
                state=1,
            )
            .first()
        )


        if not registration_type:
            raise ValueError(
                "El tipo de inscripción "
                "no es válido."
            )


        # ----------------------------------------------------
        # Se vuelve a validar en backend.
        #
        # Nunca confiamos en el hidden is_member del HTML.
        # ----------------------------------------------------

        is_member = _person_is_member(
            person.id
        )


        physical_request = (
            request.FILES.get(
                "physical_request_document"
            )
        )

        id_card = (
            request.FILES.get(
                "id_card_document"
            )
        )

        other_documents = (
            request.FILES.getlist(
                "other_documents"
            )
        )


        # ----------------------------------------------------
        # Documentos obligatorios SOLO NO SOCIO
        # ----------------------------------------------------

        if not is_member:

            if not physical_request:
                raise ValueError(
                    "Debe adjuntar la solicitud "
                    "en formato físico."
                )

            if not id_card:
                raise ValueError(
                    "Debe adjuntar el escáner "
                    "del carnet."
                )


            _validate_pdf(
                physical_request
            )

            _validate_pdf(
                id_card
            )


            for file in other_documents:
                _validate_pdf(file)


        # ----------------------------------------------------
        # Tipos base del sistema
        # ----------------------------------------------------

        request_type, _ = (
            RequestType.objects
            .get_or_create(
                type="Registration",
                defaults={
                    "state": 1
                }
            )
        )


        pending_status, _ = (
            RequestStatus.objects
            .get_or_create(
                status_type="Pending",
                defaults={
                    "state": 1
                }
            )
        )


        document_pending_status, _ = (
            RegistrationDocumentStatus.objects
            .get_or_create(
                status_type="Pending",
                defaults={
                    "state": 1
                }
            )
        )


        # ----------------------------------------------------
        # Transacción
        # ----------------------------------------------------

        with transaction.atomic():

            registration = (
                Registration.objects.create(
                    person=person,
                    registration_type=registration_type,
                    contributes_a2=int(
                        contributes_a2
                    ),
                    user=request.user,
                    user_ip=_get_client_ip(
                        request
                    ),
                )
            )


            core_request = (
                Request.objects.create(
                    request_id=registration.id,
                    request_type=request_type,
                    date=timezone.now(),
                    status=pending_status,
                )
            )


            # ------------------------------------------------
            # Documentos nuevos socios
            # ------------------------------------------------

            if not is_member:

                _, path = _save_document(
                    uploaded_file=physical_request,
                    registration=registration,
                    document_type_name=(
                        "Physical Registration Request"
                    ),
                    document_status=(
                        document_pending_status
                    ),
                    request=request,
                )

                saved_files.append(path)


                _, path = _save_document(
                    uploaded_file=id_card,
                    registration=registration,
                    document_type_name=(
                        "ID Card Scan"
                    ),
                    document_status=(
                        document_pending_status
                    ),
                    request=request,
                )

                saved_files.append(path)


                for other_file in (
                    other_documents
                ):

                    _, path = _save_document(
                        uploaded_file=other_file,
                        registration=registration,
                        document_type_name=(
                            "Other Document"
                        ),
                        document_status=(
                            document_pending_status
                        ),
                        request=request,
                    )

                    saved_files.append(path)


            # ------------------------------------------------
            # Observación inicial
            # ------------------------------------------------

            _create_observation(
                request,
                registration,
                (
                    "Registration request "
                    "created."
                )
            )


        return JsonResponse({
            "status": "ok",
            "message": (
                "Solicitud creada correctamente."
            ),
            "registration_id": registration.id,
            "request_id": core_request.id,
        })


    except ValueError as error:

        for path in saved_files:
            if default_storage.exists(path):
                default_storage.delete(path)

        return JsonResponse(
            {
                "status": "error",
                "message": str(error),
            },
            status=400,
        )


    except Exception as error:

        for path in saved_files:
            if default_storage.exists(path):
                default_storage.delete(path)

        return JsonResponse(
            {
                "status": "error",
                "message": (
                    f"Error al crear la solicitud: "
                    f"{error}"
                ),
            },
            status=500,
        )


# ============================================================
# DETALLE SOLICITUD
# ============================================================

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
        .filter(
            pk=registration_id
        )
        .first()
    )


    if not registration:
        return JsonResponse(
            {
                "status": "error",
                "message": (
                    "No se encontró la solicitud."
                )
            },
            status=404,
        )


    person = registration.person


    core_request = (
        Request.objects
        .select_related(
            "request_type",
            "status",
        )
        .filter(
            request_id=registration.id,
            request_type__type__iexact=(
                "Registration"
            ),
        )
        .order_by("-id")
        .first()
    )


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
                file_url = default_storage.url(
                    document.route
                )
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

            "date": (
                timezone.localtime(
                    document.creation_date
                ).strftime(
                    "%d-%m-%Y %H:%M"
                )
                if document.creation_date
                else ""
            ),

            "url": file_url,
        })


    observations = []


    for relation in (
        registration.observations
        .select_related(
            "observation",
            "observation__user",
        )
        .filter(
            state=1
        )
        .order_by(
            "-observation__date",
            "-observation__time",
        )
    ):

        observation = (
            relation.observation
        )


        observations.append({
            "comment": (
                observation.comment
                or ""
            ),

            "date": (
                observation.date.strftime(
                    "%d-%m-%Y"
                )
                if observation.date
                else ""
            ),

            "time": (
                observation.time.strftime(
                    "%H:%M"
                )
                if observation.time
                else ""
            ),

            "user": (
                observation.user.username
                if observation.user
                else ""
            ),
        })


    return JsonResponse({
        "status": "ok",

        "registration": {
            "id": registration.id,

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

            "type": (
                registration.registration_type.type
                if registration.registration_type
                else ""
            ),

            "contributes_a2": bool(
                registration.contributes_a2
            ),

            "status": (
                core_request.status.status_type
                if core_request
                else ""
            ),

            "date": (
                timezone.localtime(
                    core_request.date
                ).strftime(
                    "%d-%m-%Y %H:%M"
                )
                if (
                    core_request
                    and core_request.date
                )
                else ""
            ),
        },

        "documents": documents,

        "observations": observations,
    })