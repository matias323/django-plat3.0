import mimetypes
import os
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import Q

from core.models.document import Document, DocumentType
from core.models.location import Commune
from core.models.user import User, UserPermission


def clp(value):
    try:
        return "$" + f"{int(value or 0):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def date_cl(value):
    return value.strftime("%d-%m-%Y") if value else "-"


def clean_digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def person_full_name(person):
    if not person:
        return ""
    parts = [person.first_name, person.second_name, person.last_name_1, person.last_name_2]
    return " ".join(str(part).strip() for part in parts if part).strip()


def person_rut(person):
    if not person:
        return ""
    rut = f"{int(person.rut):,}".replace(",", ".") if person.rut else ""
    return f"{rut}-{person.dv}" if rut else ""


def format_rut(rut, dv=""):
    try:
        rut_text = f"{int(rut):,}".replace(",", ".")
    except (TypeError, ValueError):
        rut_text = str(rut or "").strip()
    return f"{rut_text}-{dv}" if rut_text and dv else rut_text


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")


def audit_save(instance, user=None):
    authenticated = bool(user and getattr(user, "is_authenticated", False))
    instance.save(user=user if authenticated else None)
    return instance


def get_active_session(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    try:
        session = getattr(request, "user_session", None)
        if session and getattr(session, "pk", None):
            return session
    except Exception:
        pass

    return User.get_active_session(user)


def can_view_inventory(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_active_session(request) is not None


def can_edit_inventory(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    session = get_active_session(request)
    if not session:
        return False

    # El middleware de la 3.0 autoriza escritura cuando permission_id == 2.
    # Consultamos la misma tabla core_user_permission para mantener exactamente la misma regla.
    permission = UserPermission.objects.filter(
        user=user,
        app=session.app,
        role=session.role,
        is_active=True,
        permission_id=2,
    ).exists()

    return permission or getattr(session, "permission_id", None) == 2


def is_inventory_superadmin(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    session = get_active_session(request)
    return bool(session and getattr(session, "role_id", None) == 1)


def get_document_type(name, user=None):
    document_type = DocumentType.objects.filter(name__iexact=name, is_active=True).first()
    if document_type:
        return document_type
    return audit_save(DocumentType(name=name), user)


def save_uploaded_document(request, uploaded_file, category, folder):
    if not uploaded_file:
        return None

    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension not in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("El archivo debe ser PDF o imagen.")

    internal_name = f"{uuid.uuid4().hex}{extension}"
    route = default_storage.save(f"inventario/{folder}/{internal_name}", uploaded_file)
    document_type = get_document_type(category, request.user)

    return audit_save(Document(
        user=request.user,
        type_document=document_type,
        ip=client_ip(request),
        size=uploaded_file.size,
        document_name=uploaded_file.name,
        internal_name=internal_name,
        file_type=uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or "",
        route=route,
    ), request.user)


def document_url(document):
    route = str(getattr(document, "route", "") or "")
    if not route:
        return "#"
    if route.startswith(("http://", "https://", "/")):
        return route
    try:
        return default_storage.url(route)
    except Exception:
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        return f"{media_url.rstrip('/')}/{route.lstrip('/')}"


def query_communes(term):
    term = (term or "").strip()
    if len(term) < 2:
        return []

    queryset = Commune.objects.filter(is_active=True, name__icontains=term).order_by("name")[:30]
    return [{"id": commune.id, "name": commune.name} for commune in queryset]


def commune_name(commune_id):
    if not commune_id:
        return ""
    commune = Commune.objects.filter(pk=commune_id, is_active=True).only("name").first()
    return commune.name if commune else ""


def accounting_accounts():
    # La cuenta contable no está definida en los modelos core entregados.
    # Se mantiene la tabla externa de contabilidad usada por el módulo 2.5.
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, num_cuenta, nombre FROM contab_cuenta WHERE estado = 1 "
                "ORDER BY num_cuenta ASC, nombre ASC"
            )
            return [{"id": row[0], "number": row[1], "name": row[2]} for row in cursor.fetchall()]
    except Exception:
        return []


def accounting_account(account_id):
    if not account_id:
        return {"id": None, "number": "", "name": ""}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, num_cuenta, nombre FROM contab_cuenta WHERE id = %s", [account_id])
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "number": row[1], "name": row[2]}
    except Exception:
        pass
    return {"id": None, "number": "", "name": ""}
