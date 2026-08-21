import json
import uuid
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
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
)
from core.models.partner import Partner, PartnerReentry, PartnerContributionType, PartnerContribution
from core.models.base import BaseModel
from core.models.location import Region, Commune
from core.models.person import PersonContactType, PersonContact, PersonAddress

from .models import (
    Registration,
    RegistrationType,
    RegistrationDocument,
    RegistrationDocumentStatus,
    RegistrationObservation,
)


# ============================================================
# CONFIGURACIÓN
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PARTNER_REENTRIES = 1

REGISTRATION_TYPE_INITIAL = "Registration"
REGISTRATION_TYPE_REENTRY = "Re-registration"

REQUEST_TYPE_REGISTRATION = "Registration"

REQUEST_STATUS_PENDING = "Pending"
REQUEST_STATUS_APPROVED = "Approved"
REQUEST_STATUS_REJECTED = "Rejected"

DOCUMENT_STATUS_PENDING = "Pending"
DOCUMENT_STATUS_APPROVED = "Approved"
DOCUMENT_STATUS_REJECTED = "Rejected"

DOCUMENT_TYPE_PHYSICAL = "Physical Registration Request"
DOCUMENT_TYPE_IDENTIFICATION = "Identification Document"
DOCUMENT_TYPE_OTHER = "Other Document"

CONTACT_TYPE_PHONE = "Phone"
CONTACT_TYPE_EMAIL = "Email"

CONTRIBUTION_TYPE_A2 = "A2"

DOCUMENT_TYPES = {
    "physical_request": DOCUMENT_TYPE_PHYSICAL,
    "identification": DOCUMENT_TYPE_IDENTIFICATION,
    "other": DOCUMENT_TYPE_OTHER,
}


# ============================================================
# BASEMODEL / COMPATIBILIDAD CON MODELOS CORE
def _has_field(model, field_name):
    return any(field.name == field_name for field in model._meta.get_fields())


def _save_with_user(instance, audit_user=None):
    has_audit_fields = (
        _has_field(instance.__class__, "user_create")
        and _has_field(instance.__class__, "user_update")
    )

    if has_audit_fields:
        instance.save(user=audit_user)
    else:
        instance.save()

    return instance

def _create_with_user(model, audit_user=None, **values):
    instance = model(**values)
    return _save_with_user(instance, audit_user)


def _active_filters(model, include_state=False):
    filters = {}
    if _has_field(model, "is_active"):
        filters["is_active"] = True
    if include_state and _has_field(model, "state"):
        filters["state"] = 1
    return filters


def _set_record_active(instance, active, user=None, include_state=False):
    changed = False

    if _has_field(instance.__class__, "is_active") and instance.is_active != active:
        instance.is_active = active
        changed = True

    if include_state and _has_field(instance.__class__, "state"):
        state = 1 if active else 0
        if instance.state != state:
            instance.state = state
            changed = True

    if changed:
        _save_with_user(instance, user)

    return instance


def _get_named_record(model, field_name, value, user):
    queryset = model.objects.filter(**{f"{field_name}__iexact": value})

    if _has_field(model, "is_active"):
        queryset = queryset.order_by("-is_active", "-id")
    else:
        queryset = queryset.order_by("-id")

    instance = queryset.first()

    if not instance:
        return _create_with_user(model, user, **{field_name: value})

    if _has_field(model, "is_active") and not instance.is_active:
        instance.is_active = True
        _save_with_user(instance, user)

    if _has_field(model, "state") and getattr(instance, "state", 1) != 1:
        instance.state = 1
        _save_with_user(instance, user)

    return instance


def _created_datetime(instance):
    if not instance:
        return None

    for field_name in ("created_at", "creation_date", "date"):
        value = getattr(instance, field_name, None)
        if value:
            return value

    return None


def _business_is_active(instance):
    if instance is None:
        return False
    if _has_field(instance.__class__, "state"):
        return getattr(instance, "state", 0) == 1
    return bool(getattr(instance, "is_active", True))


def _business_active_filter(model, prefix=""):
    if _has_field(model, "state"):
        return {f"{prefix}state": 1}
    if _has_field(model, "is_active"):
        return {f"{prefix}is_active": True}
    return {}


def _deactivate_queryset(queryset, model, user, include_state=True):
    values = {}

    if _has_field(model, "is_active"):
        values["is_active"] = False
    if include_state and _has_field(model, "state"):
        values["state"] = 0
    if _has_field(model, "updated_at"):
        values["updated_at"] = timezone.now()
    if _has_field(model, "user_update"):
        values["user_update"] = user

    if values:
        queryset.update(**values)


# ============================================================
# ES SOCIO?
def _is_partner_role(request):
    session = getattr(request, "user_session", None)
    role = getattr(session, "role", None) if session else None
    return bool(role and role.is_partner)


# ============================================================
# PERSONAS
def _person_full_name(person):
    parts = [person.first_name, person.second_name, person.last_name_1, person.last_name_2]
    return " ".join(str(value).strip() for value in parts if value)


def _person_rut(person):
    return f"{person.rut}-{person.dv}"


def _user_display_name(user):
    if not user:
        return ""

    person = getattr(user, "person", None)
    if person:
        name = " ".join(
            value.strip()
            for value in [
                getattr(person, "first_name", "") or "",
                getattr(person, "last_name_1", "") or "",
            ]
            if value and value.strip()
        )
        if name:
            return name

    if hasattr(user, "get_full_name"):
        name = str(user.get_full_name() or "").strip()
        if name:
            return name

    first_name = str(getattr(user, "first_name", "") or "").strip()
    last_name = str(getattr(user, "last_name", "") or "").strip()
    return " ".join(value for value in [first_name, last_name] if value) or str(
        getattr(user, "username", "") or ""
    )


# ============================================================
# CONTACTOS
def _get_active_person_contact(person, contact_type_name):
    filters = {
        "person": person,
        "contact_type__name__iexact": contact_type_name,
        **_active_filters(PersonContact, include_state=True),
    }

    return (
        PersonContact.objects
        .select_related("contact_type")
        .filter(**filters)
        .order_by("-id")
        .first()
    )


def _get_active_person_address(person):
    filters = {"person": person, **_active_filters(PersonAddress, include_state=True)}

    return (
        PersonAddress.objects
        .select_related("commune", "commune__region")
        .filter(**filters)
        .order_by("-id")
        .first()
    )


def _normalize_phone(value):
    digits = "".join(character for character in str(value or "") if character.isdigit())

    if len(digits) == 11 and digits.startswith("56"):
        digits = digits[2:]
    if len(digits) == 8:
        digits = f"9{digits}"
    if len(digits) != 9:
        raise ValueError("El teléfono debe contener 8 o 9 dígitos.")

    return digits


def _normalize_email(value):
    email = str(value or "").strip().lower()
    if not email:
        raise ValueError("Debe ingresar el correo de la persona.")

    try:
        validate_email(email)
    except ValidationError:
        raise ValueError("El correo ingresado no tiene un formato válido.")

    return email


def _get_or_create_contact_type(name, user):
    contact_type = PersonContactType.objects.filter(name__iexact=name).first()

    if not contact_type:
        values = {"name": name}
        if _has_field(PersonContactType, "state"):
            values["state"] = 1
        if _has_field(PersonContactType, "is_active"):
            values["is_active"] = True
        return _create_with_user(PersonContactType, user, **values)

    _set_record_active(contact_type, True, user, include_state=True)
    return contact_type


def _save_person_contact(person, contact_type_name, value, user):
    contact_type = _get_or_create_contact_type(contact_type_name, user)
    filters = {
        "person": person,
        "contact_type": contact_type,
        **_active_filters(PersonContact, include_state=True),
    }

    current = PersonContact.objects.filter(**filters).order_by("-id").first()
    if current and str(current.value or "").strip() == value:
        return False

    _deactivate_queryset(PersonContact.objects.filter(**filters), PersonContact, user)

    values = {"person": person, "contact_type": contact_type, "value": value}
    if _has_field(PersonContact, "state"):
        values["state"] = 1
    if _has_field(PersonContact, "is_active"):
        values["is_active"] = True
    _create_with_user(PersonContact, user, **values)
    return True


def _save_person_address(person, commune, address, number, user):
    current = _get_active_person_address(person)

    if (
        current
        and current.commune_id == commune.id
        and str(current.address or "").strip().casefold() == address.casefold()
        and str(current.number or "").strip().casefold() == number.casefold()
    ):
        return False

    filters = {"person": person, **_active_filters(PersonAddress, include_state=True)}
    _deactivate_queryset(PersonAddress.objects.filter(**filters), PersonAddress, user)

    values = {"person": person, "commune": commune, "address": address, "number": number}
    if _has_field(PersonAddress, "state"):
        values["state"] = 1
    if _has_field(PersonAddress, "is_active"):
        values["is_active"] = True
    _create_with_user(PersonAddress, user, **values)
    return True


# ============================================================
# FUNCIONES GENERALES
def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def _format_datetime(value):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%d-%m-%Y %H:%M")


def _registration_type_label(value):
    value = str(value or "").strip().lower()
    labels = {
        REGISTRATION_TYPE_INITIAL.lower(): "Inscripción",
        REGISTRATION_TYPE_REENTRY.lower(): "Reingreso",
    }
    return labels.get(value, value or "-")


def _request_status_label(value):
    value = str(value or "").strip().lower()
    labels = {
        REQUEST_STATUS_PENDING.lower(): "Pendiente",
        REQUEST_STATUS_APPROVED.lower(): "Aprobada",
        REQUEST_STATUS_REJECTED.lower(): "Rechazada",
    }
    return labels.get(value, value or "-")


def _document_status_label(value):
    value = str(value or "").strip().lower()
    labels = {
        DOCUMENT_STATUS_PENDING.lower(): "Pendiente",
        DOCUMENT_STATUS_APPROVED.lower(): "Aprobado",
        DOCUMENT_STATUS_REJECTED.lower(): "Rechazado",
    }
    return labels.get(value, value or "-")


def _document_type_label(value):
    value = str(value or "").strip()
    labels = {
        DOCUMENT_TYPE_PHYSICAL: "Solicitud firmada",
        DOCUMENT_TYPE_IDENTIFICATION: "Documento de identificación",
        DOCUMENT_TYPE_OTHER: "Otro documento",
    }
    return labels.get(value, value or "-")


# ============================================================
# FUNCIONARIOS
def _find_employee_by_code(code):
    employee = (
        Employee.objects
        .select_related("person", "grade")
        .filter(code__iexact=str(code).strip())
        .first()
    )

    if not employee:
        return None

    return {
        "person": employee.person,
        "code": employee.code,
        "grade": employee.grade.name if getattr(employee, "grade", None) else "",
    }


def _employee_codes(person_ids):
    if not person_ids:
        return {}
    return {
        employee["person_id"]: employee["code"]
        for employee in Employee.objects.filter(person_id__in=person_ids).values("person_id", "code")
    }


def _person_ids_by_employee_code(search):
    if not search:
        return []
    return list(Employee.objects.filter(code__icontains=search).values_list("person_id", flat=True))


# ============================================================
# REQUEST / TIPOS / ESTADOS
def _get_core_request(registration):
    return registration.request if registration else None


def _get_request_type(type_name, user):
    return _get_named_record(RequestType, "name", type_name, user)


def _get_request_status(status_type, user):
    return _get_named_record(RequestStatus, "status_type", status_type, user)


def _get_registration_type(situation, user):
    return _get_named_record(RegistrationType, "type", situation["type"], user)


def _get_registration_document_status(status_type, user):
    return _get_named_record(RegistrationDocumentStatus, "status_type", status_type, user)


def _get_document_type(type_name, user):
    return _get_named_record(DocumentType, "name", type_name, user)


def _get_a2_contribution_type():
    contribution_type = (
        PartnerContributionType.objects
        .filter(is_active=True)
        .filter(
            Q(discount_code__iexact=CONTRIBUTION_TYPE_A2)
            | Q(description__iexact=CONTRIBUTION_TYPE_A2)
            | Q(description__icontains=CONTRIBUTION_TYPE_A2)
        )
        .order_by("id")
        .first()
    )

    if not contribution_type:
        raise ValueError(
            "No existe un tipo de aporte A2 activo. "
            "Configure A2 en Tipos de Aporte antes de aprobar la solicitud."
        )

    return contribution_type


# ============================================================
# SITUACIÓN SOCIO
def _get_partner_situation(person):
    partner = Partner.objects.filter(person=person).first()

    if not partner:
        return {
            "allowed": True,
            "partner": None,
            "type": REGISTRATION_TYPE_INITIAL,
            "member_status": "No socio",
            "is_reentry": False,
            "reentries_used": 0,
        }

    if _business_is_active(partner):
        return {
            "allowed": False,
            "partner": partner,
            "message": "El funcionario ya es socio activo.",
        }

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


# ============================================================
# DOCUMENTOS
def _validate_pdf(uploaded_file):
    if not uploaded_file:
        raise ValueError("Debe adjuntar un documento.")

    extension = Path(uploaded_file.name).suffix.lower()
    if extension != ".pdf":
        raise ValueError(f'El archivo "{uploaded_file.name}" debe estar en formato PDF.')
    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValueError(f'El archivo "{uploaded_file.name}" supera el máximo de 10 MB.')


def _save_document(*, uploaded_file, registration, document_type_name, document_status, request):
    _validate_pdf(uploaded_file)
    document_type = _get_document_type(document_type_name, request.user)

    internal_name = uuid.uuid4().hex
    extension = Path(uploaded_file.name).suffix.lower()
    relative_path = f"registrations/{registration.id}/{internal_name}{extension}"
    saved_path = default_storage.save(relative_path, uploaded_file)

    values = {
        "type_document": document_type,
        "ip": _get_client_ip(request),
        "size": uploaded_file.size,
        "document_name": uploaded_file.name,
        "internal_name": internal_name,
        "file_type": uploaded_file.content_type or "application/pdf",
        "route": saved_path,
    }

    if _has_field(Document, "user"):
        values["user"] = request.user

    document = _create_with_user(Document, request.user, **values)
    relation = _create_with_user(
        RegistrationDocument,
        request.user,
        registration=registration,
        document=document,
        status=document_status,
    )

    return relation, saved_path


def _document_relations_by_type(registration, document_type_name):
    return (
        RegistrationDocument.objects
        .filter(
            registration=registration,
            is_active=True,
            document__type_document__name__iexact=document_type_name,
        )
        .select_related("status", "document", "document__type_document")
    )


def _document_upload_rule(registration, document_type_name):
    if document_type_name == DOCUMENT_TYPE_OTHER:
        return {"allowed": True, "reason": ""}

    relations = _document_relations_by_type(registration, document_type_name)

    if relations.filter(status__status_type__iexact=DOCUMENT_STATUS_PENDING).exists():
        return {
            "allowed": False,
            "reason": (
                f"Ya existe un documento de tipo {_document_type_label(document_type_name)} "
                f"pendiente de revisión."
            ),
        }

    if relations.filter(status__status_type__iexact=DOCUMENT_STATUS_APPROVED).exists():
        return {
            "allowed": False,
            "reason": f"Ya existe un documento de tipo {_document_type_label(document_type_name)} aprobado.",
        }

    return {"allowed": True, "reason": ""}


def _document_upload_rules(registration):
    return {
        "physical_request": _document_upload_rule(registration, DOCUMENT_TYPE_PHYSICAL),
        "identification": _document_upload_rule(registration, DOCUMENT_TYPE_IDENTIFICATION),
        "other": {"allowed": True, "reason": ""},
    }


def _registration_document_approval_state(registration):
    relations = (
        RegistrationDocument.objects
        .filter(registration=registration, is_active=True)
        .select_related("status", "document", "document__type_document")
    )

    has_pending = relations.filter(status__status_type__iexact=DOCUMENT_STATUS_PENDING).exists()
    physical_approved = relations.filter(
        document__type_document__name__iexact=DOCUMENT_TYPE_PHYSICAL,
        status__status_type__iexact=DOCUMENT_STATUS_APPROVED,
    ).exists()
    identification_approved = relations.filter(
        document__type_document__name__iexact=DOCUMENT_TYPE_IDENTIFICATION,
        status__status_type__iexact=DOCUMENT_STATUS_APPROVED,
    ).exists()

    reasons = []
    if has_pending:
        reasons.append("Existen documentos pendientes de revisión.")
    if not physical_approved:
        reasons.append("La solicitud firmada debe estar aprobada.")
    if not identification_approved:
        reasons.append("El documento de identificación debe estar aprobado.")

    return {
        "can_approve": not has_pending and physical_approved and identification_approved,
        "has_pending": has_pending,
        "physical_approved": physical_approved,
        "identification_approved": identification_approved,
        "reasons": reasons,
    }


# ============================================================
# OBSERVACIONES
def _create_observation(request, registration, comment):
    values = {"comment": comment}

    if _has_field(Observation, "user"):
        values["user"] = request.user
    if _has_field(Observation, "date"):
        values["date"] = timezone.localdate()
    if _has_field(Observation, "time"):
        values["time"] = timezone.localtime().time()
    if _has_field(Observation, "ip"):
        values["ip"] = _get_client_ip(request)

    observation = _create_with_user(Observation, request.user, **values)
    _create_with_user(
        RegistrationObservation,
        request.user,
        registration=registration,
        observation=observation,
    )
    return observation


def _observation_datetime(observation):
    created_at = getattr(observation, "created_at", None)
    if created_at:
        return _format_datetime(created_at)

    date = getattr(observation, "date", None)
    time = getattr(observation, "time", None)
    date_text = date.strftime("%d-%m-%Y") if date else ""
    time_text = time.strftime("%H:%M") if time else ""
    return " ".join(value for value in [date_text, time_text] if value)


def _observation_user(observation):
    return getattr(observation, "user_create", None) or getattr(observation, "user", None)


# ============================================================
# APROBAR INGRESO / REINGRESO SOCIO
def _process_approved_partner_registration(registration, core_request, user):
    existing_entry = PartnerReentry.objects.filter(request=core_request).first()
    if existing_entry:
        return existing_entry.partner

    registration_type = str(registration.registration_type.type or "").strip()
    is_reentry = registration_type.lower() == REGISTRATION_TYPE_REENTRY.lower()

    partner = Partner.objects.select_for_update().filter(person=registration.person).first()
    today = timezone.localdate()

    if not is_reentry:
        if partner:
            if partner.is_active:
                raise ValueError("El funcionario ya se encuentra registrado como socio activo.")
            raise ValueError(
                "El funcionario ya posee un registro de socio. "
                "La solicitud debería corresponder a un reingreso."
            )

        partner = _create_with_user(
            Partner,
            user,
            person=registration.person,
            is_active=True,
        )

    else:
        if not partner:
            raise ValueError("No existe un registro de socio para realizar el reingreso.")
        if partner.is_active:
            raise ValueError("El funcionario ya se encuentra como socio activo.")

        total_entries = PartnerReentry.objects.filter(partner=partner).count()
        reentries_used = max(total_entries - 1, 0)
        if reentries_used >= MAX_PARTNER_REENTRIES:
            raise ValueError("El socio ya utilizó la cantidad máxima de reingresos permitidos.")

        _deactivate_queryset(
            PartnerReentry.objects.filter(partner=partner, is_active=True),
            PartnerReentry,
            user,
            include_state=False,
        )

        partner.is_active = True
        _save_with_user(partner, user)

    _create_with_user(
        PartnerReentry,
        user,
        partner=partner,
        request=core_request,
        entry_date=today,
        resignation_date=None,
        is_active=True,
    )

    contribution_type = _get_a2_contribution_type()
    contribution_amount = registration.contributes_a2 or 0

    _deactivate_queryset(
        PartnerContribution.objects.filter(
            partner=partner,
            contribution_type=contribution_type,
            is_active=True,
        ),
        PartnerContribution,
        user,
        include_state=False,
    )

    _create_with_user(
        PartnerContribution,
        user,
        partner=partner,
        contribution_type=contribution_type,
        amount=contribution_amount,
        is_active=True,
    )

    return partner


# ============================================================
# VISTA PRINCIPAL
@login_required
def registration_list(request):
    # ========================================================
    # USUARIO CON ROL SOCIO
    # ========================================================
    if _is_partner_role(request):
        regions = Region.objects.filter(is_active=True).order_by("name")

        context = {
            "regions": regions,
            "can_create": False,
            "message": "",
            "message_type": "info",
        }

        person = getattr(request.user, "person", None)

        if not person:
            context["message"] = "Tu usuario no se encuentra asociado a una persona."
            context["message_type"] = "danger"
            return render(request, "inscripcion/registration_self.html", context)

        employee = (
            Employee.objects
            .select_related("person", "grade")
            .filter(person=person)
            .first()
        )

        if not employee:
            context["message"] = "Tu usuario no se encuentra asociado a un funcionario."
            context["message_type"] = "danger"
            return render(request, "inscripcion/registration_self.html", context)

        # ====================================================
        # SOLICITUD PENDIENTE
        # ====================================================
        has_pending = (
            Registration.objects
            .filter(
                person=person,
                is_active=True,
                request__request_type__name__iexact=REQUEST_TYPE_REGISTRATION,
                request__status__status_type__iexact=REQUEST_STATUS_PENDING,
            )
            .exists()
        )

        if has_pending:
            context["message"] = "Ya tienes una solicitud de inscripción pendiente de revisión."
            context["message_type"] = "warning"
            return render(request, "inscripcion/registration_self.html", context)

        # ====================================================
        # SITUACIÓN ACTUAL DEL SOCIO
        # ====================================================
        situation = _get_partner_situation(person)

        if not situation["allowed"]:
            context["message"] = situation.get(
                "message",
                "Actualmente no puedes generar una solicitud de inscripción.",
            )
            context["message_type"] = "info"

            return render(
                request,
                "inscripcion/registration_self.html",
                context,
            )

        registration_type = _get_registration_type(
            situation,
            request.user,
        )

        phone_contact = _get_active_person_contact(
            person,
            CONTACT_TYPE_PHONE,
        )

        email_contact = _get_active_person_contact(
            person,
            CONTACT_TYPE_EMAIL,
        )

        person_address = _get_active_person_address(person)

        # ====================================================
        # FORMULARIO AUTOSERVICIO
        # ====================================================
        context.update({
            "can_create": True,

            "employee": {
                "person_id": person.id,
                "code": employee.code,
                "rut": _person_rut(person),
                "name": _person_full_name(person),

                "grade": (
                    employee.grade.name
                    if getattr(employee, "grade", None)
                    else ""
                ),

                "member_status": situation["member_status"],
            },

            "registration_type": {
                "id": registration_type.id,
                "type": registration_type.type,
                "display_name": _registration_type_label(
                    registration_type.type
                ),
                "is_reentry": situation["is_reentry"],
            },

            "phone": (
                phone_contact.value
                if phone_contact
                else ""
            ),

            "email": (
                email_contact.value
                if email_contact
                else ""
            ),

            "address": (
                person_address.address
                if person_address
                else ""
            ),

            "address_number": (
                person_address.number
                if person_address
                else ""
            ),

            "region_id": (
                person_address.commune.region_id
                if person_address and person_address.commune
                else None
            ),

            "commune_id": (
                person_address.commune_id
                if person_address
                else None
            ),
        })

        return render(
            request,
            "inscripcion/registration_self.html",
            context,
        )

    # ========================================================
    # USUARIO ADMINISTRATIVO
    # ========================================================
    regions = Region.objects.filter(
        is_active=True,
    ).order_by("name")

    return render(
        request,
        "inscripcion/registration_list.html",
        {
            "regions": regions,
        },
    )


# ============================================================
# COMUNAS POR REGIÓN
@login_required
@require_GET
def communes_by_region(request, region_id):
    communes = (
        Commune.objects
        .filter(region_id=region_id, is_active=True, region__is_active=True)
        .order_by("name")
        .values("id", "name")
    )
    return JsonResponse({"status": "ok", "communes": list(communes)})


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

        queryset = (
            Registration.objects
            .filter(is_active=True)
            .select_related(
                "person",
                "registration_type",
                "request",
                "request__status",
                "request__request_type",
            )
            .order_by("-id")
        )

        records_total = queryset.count()

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
        registrations = list(queryset[start:start + length])
        person_ids = [item.person_id for item in registrations if item.person_id]
        employee_codes = _employee_codes(person_ids)
        data = []

        for registration in registrations:
            person = registration.person
            core_request = registration.request
            request_status = (
                core_request.status.status_type
                if core_request and core_request.status
                else ""
            )

            data.append({
                "id": registration.id,
                "employee_code": employee_codes.get(registration.person_id, ""),
                "rut": _person_rut(person) if person else "",
                "employee_name": _person_full_name(person) if person else "",
                "registration_type": _registration_type_label(
                    registration.registration_type.type if registration.registration_type else ""
                ),
                "contributes_a2": registration.contributes_a2 or 0,
                "date": _format_datetime(_created_datetime(core_request)),
                "status": _request_status_label(request_status),
                "status_code": request_status,
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
        has_pending = Registration.objects.filter(
            person=person,
            is_active=True,
            request__request_type__name__iexact=REQUEST_TYPE_REGISTRATION,
            request__status__status_type__iexact=REQUEST_STATUS_PENDING,
        ).exists()

        if has_pending:
            return JsonResponse({
                "status": "error",
                "message": "El funcionario ya posee una solicitud de inscripción pendiente.",
            }, status=400)

        situation = _get_partner_situation(person)
        if not situation["allowed"]:
            return JsonResponse({
                "status": "error",
                "message": situation["message"],
            }, status=400)

        registration_type = _get_registration_type(situation, request.user)
        phone_contact = _get_active_person_contact(person, CONTACT_TYPE_PHONE)
        email_contact = _get_active_person_contact(person, CONTACT_TYPE_EMAIL)
        person_address = _get_active_person_address(person)

        return JsonResponse({
            "status": "ok",
            "employee": {
                "person_id": person.id,
                "code": employee["code"],
                "rut": _person_rut(person),
                "name": _person_full_name(person),
                "grade": employee["grade"],
                "member_status": situation["member_status"],
                "phone": phone_contact.value if phone_contact else "",
                "email": email_contact.value if email_contact else "",
                "address": person_address.address if person_address else "",
                "address_number": person_address.number if person_address else "",
                "commune_id": person_address.commune_id if person_address else None,
                "region_id": (
                    person_address.commune.region_id
                    if person_address and person_address.commune
                    else None
                ),
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
        return JsonResponse({"status": "error", "message": str(error)}, status=500)


# ============================================================
# CREAR SOLICITUD
@login_required
@require_POST
def create_registration(request):
    saved_files = []

    try:
        try:
            person_id = int(request.POST.get("person_id", 0))
        except (TypeError, ValueError):
            person_id = 0

        if _is_partner_role(request):
            current_person = getattr(request.user, "person", None)
            if not current_person:
                raise ValueError("Tu usuario no se encuentra asociado a una persona.")
            person_id = current_person.id

        try:
            registration_type_id = int(request.POST.get("registration_type", 0))
        except (TypeError, ValueError):
            registration_type_id = 0

        try:
            region_id = int(request.POST.get("region_id", 0))
        except (TypeError, ValueError):
            region_id = 0

        try:
            commune_id = int(request.POST.get("commune_id", 0))
        except (TypeError, ValueError):
            commune_id = 0

        try:
            contributes_a2 = int(request.POST.get("contributes_a2", "0"))
        except (TypeError, ValueError):
            raise ValueError("El aporte A2 debe ser un valor numérico.")

        phone = _normalize_phone(request.POST.get("phone", ""))
        email = _normalize_email(request.POST.get("email", ""))
        address = str(request.POST.get("address", "")).strip()
        address_number = str(request.POST.get("address_number", "")).strip()

        if contributes_a2 < 0:
            raise ValueError("El aporte A2 no puede ser negativo.")
        if person_id <= 0:
            raise ValueError("Debe seleccionar un funcionario.")
        if registration_type_id <= 0:
            raise ValueError("No se pudo determinar el tipo de solicitud.")
        if region_id <= 0:
            raise ValueError("Debe seleccionar una región.")
        if commune_id <= 0:
            raise ValueError("Debe seleccionar una comuna.")
        if not address:
            raise ValueError("Debe ingresar la dirección de la persona.")
        if not address_number:
            raise ValueError("Debe ingresar el número de la dirección.")

        person = Person.objects.filter(pk=person_id).first()
        if not person:
            raise ValueError("La persona seleccionada no existe.")
        if not Employee.objects.filter(person=person).exists():
            raise ValueError("La persona seleccionada no corresponde a un funcionario.")

        commune = (
            Commune.objects
            .select_related("region")
            .filter(
                pk=commune_id,
                region_id=region_id,
                is_active=True,
                region__is_active=True,
            )
            .first()
        )
        if not commune:
            raise ValueError("La comuna seleccionada no pertenece a la región indicada.")

        situation = _get_partner_situation(person)
        if not situation["allowed"]:
            raise ValueError(situation["message"])

        expected_registration_type = _get_registration_type(situation, request.user)
        if registration_type_id != expected_registration_type.id:
            raise ValueError("El tipo de solicitud no corresponde al estado actual del funcionario.")

        has_pending = Registration.objects.filter(
            person=person,
            is_active=True,
            request__request_type__name__iexact=REQUEST_TYPE_REGISTRATION,
            request__status__status_type__iexact=REQUEST_STATUS_PENDING,
        ).exists()
        if has_pending:
            raise ValueError("El funcionario ya posee una solicitud de inscripción pendiente.")

        physical_request = request.FILES.get("physical_request_document")
        identification_document = request.FILES.get("identification_document")
        other_documents = request.FILES.getlist("other_documents")

        _validate_pdf(physical_request)
        _validate_pdf(identification_document)
        for uploaded_file in other_documents:
            _validate_pdf(uploaded_file)

        request_type = _get_request_type(REQUEST_TYPE_REGISTRATION, request.user)
        pending_status = _get_request_status(REQUEST_STATUS_PENDING, request.user)
        document_pending_status = _get_registration_document_status(DOCUMENT_STATUS_PENDING, request.user)

        with transaction.atomic():
            core_request = _create_with_user(
                Request,
                request.user,
                request_type=request_type,
                status=pending_status,
            )

            registration = _create_with_user(
                Registration,
                request.user,
                request=core_request,
                person=person,
                registration_type=expected_registration_type,
                contributes_a2=contributes_a2,
                user_ip=_get_client_ip(request),
            )

            phone_changed = _save_person_contact(person, CONTACT_TYPE_PHONE, phone, request.user)
            email_changed = _save_person_contact(person, CONTACT_TYPE_EMAIL, email, request.user)
            address_changed = _save_person_address(person, commune, address, address_number, request.user)

            contact_comment = (
                "Datos de contacto y domicilio actualizados."
                if phone_changed or email_changed or address_changed
                else "Datos de contacto y domicilio confirmados sin cambios."
            )
            _create_observation(request, registration, contact_comment)

            _, path = _save_document(
                uploaded_file=physical_request,
                registration=registration,
                document_type_name=DOCUMENT_TYPE_PHYSICAL,
                document_status=document_pending_status,
                request=request,
            )
            saved_files.append(path)
            _create_observation(
                request,
                registration,
                f"Documento adjuntado: {_document_type_label(DOCUMENT_TYPE_PHYSICAL)}.",
            )

            _, path = _save_document(
                uploaded_file=identification_document,
                registration=registration,
                document_type_name=DOCUMENT_TYPE_IDENTIFICATION,
                document_status=document_pending_status,
                request=request,
            )
            saved_files.append(path)
            _create_observation(
                request,
                registration,
                f"Documento adjuntado: {_document_type_label(DOCUMENT_TYPE_IDENTIFICATION)}.",
            )

            for other_file in other_documents:
                _, path = _save_document(
                    uploaded_file=other_file,
                    registration=registration,
                    document_type_name=DOCUMENT_TYPE_OTHER,
                    document_status=document_pending_status,
                    request=request,
                )
                saved_files.append(path)
                _create_observation(
                    request,
                    registration,
                    f"Documento adjuntado: Otro documento ({other_file.name}).",
                )

            action_name = "reingreso" if situation["is_reentry"] else "inscripción"
            _create_observation(request, registration, f"Solicitud de {action_name} creada.")

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
        return JsonResponse({"status": "error", "message": str(error)}, status=400)

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
        .filter(pk=registration_id, is_active=True)
        .select_related(
            "person",
            "registration_type",
            "request",
            "request__status",
            "request__request_type",
        )
        .first()
    )

    if not registration:
        return JsonResponse({
            "status": "error",
            "message": "No se encontró la solicitud.",
        }, status=404)

    person = registration.person
    core_request = _get_core_request(registration)
    documents = []

    document_order = "-document__created_at" if _has_field(Document, "created_at") else "-document__creation_date"

    for relation in (
        registration.documents
        .filter(is_active=True)
        .select_related("document", "document__type_document", "status")
        .order_by(document_order, "-id")
    ):
        document = relation.document
        file_url = ""

        if document.route:
            try:
                file_url = default_storage.url(document.route)
            except Exception:
                file_url = document.route

        document_status = relation.status.status_type if relation.status else ""
        document_type = document.type_document.name if document.type_document else ""

        documents.append({
            "relation_id": relation.id,
            "id": document.id,
            "name": document.document_name,
            "type": _document_type_label(document_type),
            "type_code": document_type,
            "status": _document_status_label(document_status),
            "status_code": document_status,
            "date": _format_datetime(_created_datetime(document)),
            "url": file_url,
        })

    observations = []
    observation_relations = (
        registration.observations
        .filter(is_active=True)
        .select_related("observation")
        .order_by("-created_at", "-id")
    )

    for relation in observation_relations:
        observation = relation.observation
        observations.append({
            "comment": observation.comment or "",
            "datetime": _observation_datetime(observation),
            "user": _user_display_name(_observation_user(observation)),
        })

    request_status = (
        core_request.status.status_type
        if core_request and core_request.status
        else ""
    )
    request_is_pending = request_status.lower() == REQUEST_STATUS_PENDING.lower()
    document_approval = _registration_document_approval_state(registration)

    employee_code = ""
    phone_contact = _get_active_person_contact(person, CONTACT_TYPE_PHONE) if person else None
    email_contact = _get_active_person_contact(person, CONTACT_TYPE_EMAIL) if person else None
    person_address = _get_active_person_address(person) if person else None

    if person:
        employee_code = (
            Employee.objects
            .filter(person=person)
            .values_list("code", flat=True)
            .first()
            or ""
        )

    document_upload = _document_upload_rules(registration)
    document_upload["can_add"] = request_is_pending

    return JsonResponse({
        "status": "ok",
        "registration": {
            "id": registration.id,
            "employee_code": employee_code,
            "rut": _person_rut(person) if person else "",
            "name": _person_full_name(person) if person else "",
            "type": _registration_type_label(
                registration.registration_type.type if registration.registration_type else ""
            ),
            "contributes_a2": registration.contributes_a2 or 0,
            "status": _request_status_label(request_status),
            "status_code": request_status,
            "date": _format_datetime(_created_datetime(core_request)),
            "phone": phone_contact.value if phone_contact else "",
            "email": email_contact.value if email_contact else "",
            "address": person_address.address if person_address else "",
            "address_number": person_address.number if person_address else "",
            "commune": person_address.commune.name if person_address else "",
            "region": (
                person_address.commune.region.name
                if person_address and person_address.commune and person_address.commune.region
                else ""
            ),
        },
        "documents": documents,
        "observations": observations,
        "document_upload": document_upload,
        "management": {
            "can_change_status": request_is_pending,
            "can_approve": request_is_pending and document_approval["can_approve"],
            "document_validation": {
                "has_pending": document_approval["has_pending"],
                "physical_approved": document_approval["physical_approved"],
                "identification_approved": document_approval["identification_approved"],
                "reasons": document_approval["reasons"],
            },
        },
    })


# ============================================================
# AGREGAR DOCUMENTO
@login_required
@require_POST
def add_registration_document(request, registration_id):
    saved_path = None

    try:
        registration = (
            Registration.objects
            .select_related("request", "request__status")
            .filter(pk=registration_id, is_active=True)
            .first()
        )
        if not registration:
            raise ValueError("No se encontró la solicitud.")

        core_request = registration.request
        request_status = (
            core_request.status.status_type
            if core_request and core_request.status
            else ""
        )
        if request_status.lower() != REQUEST_STATUS_PENDING.lower():
            raise ValueError(
                "No se pueden adjuntar documentos porque la solicitud ya fue aprobada o rechazada."
            )

        document_type_key = str(request.POST.get("document_type", "")).strip()
        uploaded_file = request.FILES.get("document")
        document_type_name = DOCUMENT_TYPES.get(document_type_key)

        if not document_type_name:
            raise ValueError("Debe seleccionar un tipo de documento válido.")

        _validate_pdf(uploaded_file)

        if document_type_name != DOCUMENT_TYPE_OTHER:
            rule = _document_upload_rule(registration, document_type_name)
            if not rule["allowed"]:
                raise ValueError(rule["reason"])

        had_rejected = _document_relations_by_type(registration, document_type_name).filter(
            status__status_type__iexact=DOCUMENT_STATUS_REJECTED
        ).exists()

        pending_status = _get_registration_document_status(DOCUMENT_STATUS_PENDING, request.user)

        with transaction.atomic():
            _, saved_path = _save_document(
                uploaded_file=uploaded_file,
                registration=registration,
                document_type_name=document_type_name,
                document_status=pending_status,
                request=request,
            )

            document_label = _document_type_label(document_type_name)
            if document_type_name == DOCUMENT_TYPE_OTHER:
                comment = f"Documento adicional adjuntado: {uploaded_file.name}."
            elif had_rejected:
                comment = (
                    f"Nuevo documento adjuntado tras rechazo: {document_label}. "
                    f"Archivo: {uploaded_file.name}."
                )
            else:
                comment = f"Documento adjuntado: {document_label}. Archivo: {uploaded_file.name}."

            _create_observation(request, registration, comment)

        return JsonResponse({
            "status": "ok",
            "message": "Documento adjuntado correctamente y enviado a revisión.",
        })

    except ValueError as error:
        if saved_path and default_storage.exists(saved_path):
            default_storage.delete(saved_path)
        return JsonResponse({"status": "error", "message": str(error)}, status=400)

    except Exception as error:
        if saved_path and default_storage.exists(saved_path):
            default_storage.delete(saved_path)
        return JsonResponse({
            "status": "error",
            "message": f"Error al adjuntar el documento: {error}",
        }, status=500)


# ============================================================
# CAMBIAR ESTADO DOCUMENTO
@login_required
@require_POST
def update_document_status(request, registration_id, document_relation_id):
    try:
        body = json.loads(request.body or "{}")
        new_status = str(body.get("status", "")).strip()
        reason = str(body.get("reason", "")).strip()

        allowed_statuses = {
            DOCUMENT_STATUS_APPROVED.lower(): DOCUMENT_STATUS_APPROVED,
            DOCUMENT_STATUS_REJECTED.lower(): DOCUMENT_STATUS_REJECTED,
        }
        normalized_status = allowed_statuses.get(new_status.lower())

        if not normalized_status:
            raise ValueError("El estado seleccionado no es válido.")
        if normalized_status == DOCUMENT_STATUS_REJECTED and len(reason) < 5:
            raise ValueError("Debe indicar el motivo del rechazo.")

        with transaction.atomic():
            relation = (
                RegistrationDocument.objects
                .select_for_update()
                .select_related("status", "document", "document__type_document", "registration")
                .filter(
                    pk=document_relation_id,
                    registration_id=registration_id,
                    is_active=True,
                )
                .first()
            )
            if not relation:
                raise ValueError("No se encontró el documento asociado a la solicitud.")

            registration = (
                Registration.objects
                .select_related("request", "request__status")
                .filter(pk=relation.registration_id, is_active=True)
                .first()
            )
            if not registration:
                raise ValueError("No se encontró la solicitud.")

            request_status = (
                registration.request.status.status_type
                if registration.request and registration.request.status
                else ""
            )
            if request_status.lower() != REQUEST_STATUS_PENDING.lower():
                raise ValueError(
                    "No se puede modificar el estado de documentos porque la solicitud ya fue aprobada o rechazada."
                )

            current_status = relation.status.status_type if relation.status else ""
            if current_status.lower() in (
                DOCUMENT_STATUS_APPROVED.lower(),
                DOCUMENT_STATUS_REJECTED.lower(),
            ):
                raise ValueError("El documento ya fue gestionado y no puede volver a modificarse.")

            status_object = _get_registration_document_status(normalized_status, request.user)
            relation.status = status_object
            _save_with_user(relation, request.user)

            document_type = (
                relation.document.type_document.name
                if relation.document and relation.document.type_document
                else ""
            )
            document_label = _document_type_label(document_type)

            if normalized_status == DOCUMENT_STATUS_APPROVED:
                comment = f"Documento validado: {document_label}."
            else:
                comment = f"Documento rechazado: {document_label}. Motivo: {reason}"

            _create_observation(request, registration, comment)

        return JsonResponse({
            "status": "ok",
            "message": (
                "Documento aprobado correctamente."
                if normalized_status == DOCUMENT_STATUS_APPROVED
                else "Documento rechazado correctamente. Puede adjuntar uno nuevo de este tipo."
            ),
        })

    except ValueError as error:
        return JsonResponse({"status": "error", "message": str(error)}, status=400)
    except Exception as error:
        return JsonResponse({
            "status": "error",
            "message": f"Error al actualizar el documento: {error}",
        }, status=500)


# ============================================================
# CAMBIAR ESTADO SOLICITUD
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
            raise ValueError("El estado seleccionado no es válido.")

        with transaction.atomic():
            registration = (
                Registration.objects
                .select_for_update()
                .select_related("registration_type")
                .filter(pk=registration_id, is_active=True)
                .first()
            )
            if not registration:
                raise ValueError("No se encontró la solicitud.")

            core_request = (
                Request.objects
                .select_for_update()
                .select_related("status", "request_type")
                .filter(pk=registration.request_id)
                .first()
            )
            if not core_request:
                raise ValueError("La solicitud no posee un Request asociado.")

            current_status = str(
                core_request.status.status_type if core_request.status else ""
            ).strip()

            if current_status.lower() in (
                REQUEST_STATUS_APPROVED.lower(),
                REQUEST_STATUS_REJECTED.lower(),
            ):
                raise ValueError("La solicitud ya se encuentra en un estado final.")
            if current_status.lower() != REQUEST_STATUS_PENDING.lower():
                raise ValueError("Solo se pueden gestionar solicitudes pendientes.")

            if normalized_status == REQUEST_STATUS_APPROVED:
                document_approval = _registration_document_approval_state(registration)
                if not document_approval["can_approve"]:
                    reasons = " ".join(document_approval["reasons"])
                    raise ValueError("La solicitud todavía no puede ser aprobada. " + reasons)

                _process_approved_partner_registration(
                    registration=registration,
                    core_request=core_request,
                    user=request.user,
                )

            status_object = _get_request_status(normalized_status, request.user)
            core_request.status = status_object
            _save_with_user(core_request, request.user)

            status_label = "aprobada" if normalized_status == REQUEST_STATUS_APPROVED else "rechazada"
            _create_observation(request, registration, f"Solicitud {status_label}.")

        return JsonResponse({
            "status": "ok",
            "message": f"Solicitud {status_label} correctamente.",
        })

    except ValueError as error:
        return JsonResponse({"status": "error", "message": str(error)}, status=400)
    except Exception as error:
        return JsonResponse({
            "status": "error",
            "message": f"Error al actualizar la solicitud: {error}",
        }, status=500)


# ============================================================
# SOLICITUD INSCRIPCION SOCIO
@login_required
def registration_self_service(request):
    if not _is_partner_role(request):
        return redirect("registrations:list")

    regions = Region.objects.filter(is_active=True).order_by("name")

    context = {
        "regions": regions,
        "can_create": False,
        "message": "",
        "message_type": "info",
    }

    person = getattr(request.user, "person", None)

    if not person:
        context["message"] = "Tu usuario no se encuentra asociado a una persona."
        context["message_type"] = "danger"
        return render(request, "inscripcion/registration_self.html", context)

    employee = (
        Employee.objects
        .select_related("person", "grade")
        .filter(person=person)
        .first()
    )

    if not employee:
        context["message"] = "Tu usuario no se encuentra asociado a un funcionario."
        context["message_type"] = "danger"
        return render(request, "inscripcion/registration_self.html", context)

    has_pending = (
        Registration.objects
        .filter(
            person=person,
            is_active=True,
            request__request_type__name__iexact=REQUEST_TYPE_REGISTRATION,
            request__status__status_type__iexact=REQUEST_STATUS_PENDING,
        )
        .exists()
    )

    if has_pending:
        context["message"] = "Ya tienes una solicitud de inscripción pendiente de revisión."
        context["message_type"] = "warning"
        return render(request, "inscripcion/registration_self.html", context)

    situation = _get_partner_situation(person)

    if not situation["allowed"]:
        context["message"] = situation.get(
            "message",
            "Actualmente no puedes generar una solicitud de inscripción.",
        )
        return render(request, "inscripcion/registration_self.html", context)

    registration_type = _get_registration_type(situation, request.user)
    phone_contact = _get_active_person_contact(person, CONTACT_TYPE_PHONE)
    email_contact = _get_active_person_contact(person, CONTACT_TYPE_EMAIL)
    person_address = _get_active_person_address(person)

    context.update({
        "can_create": True,

        "employee": {
            "person_id": person.id,
            "code": employee.code,
            "rut": _person_rut(person),
            "name": _person_full_name(person),
            "grade": employee.grade.name if getattr(employee, "grade", None) else "",
            "member_status": situation["member_status"],
        },

        "registration_type": {
            "id": registration_type.id,
            "type": registration_type.type,
            "display_name": _registration_type_label(registration_type.type),
            "is_reentry": situation["is_reentry"],
        },

        "phone": phone_contact.value if phone_contact else "",
        "email": email_contact.value if email_contact else "",
        "address": person_address.address if person_address else "",
        "address_number": person_address.number if person_address else "",
        "region_id": (
            person_address.commune.region_id
            if person_address and person_address.commune
            else None
        ),
        "commune_id": person_address.commune_id if person_address else None,
    })

    return render(request, "inscripcion/registration_self.html", context)