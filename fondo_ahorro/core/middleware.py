from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.functional import SimpleLazyObject

from applications.apps.models import App
from core.models.user import User, UserPermission


class ActiveAppSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_session = SimpleLazyObject(
            lambda: User.get_active_session(request.user) if request.user.is_authenticated else None
        )

        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        resolver = request.resolver_match

        # ====================================================
        # RUTAS QUE NO DEBEN VALIDAR LA SESIÓN DE APLICACIÓN
        # ====================================================
        if resolver and resolver.url_name in {
            "login",
            "logout",
            "register",
            "perfil",
        }:
            return None

        # ====================================================
        # USUARIO NO AUTENTICADO
        # ====================================================
        if not request.user.is_authenticated:
            return None  

        # Obtenemos la sesión activa de forma segura
        session = User.get_active_session(request.user)

        if not session:
           
            return redirect('core:logout') 

        # ====================================================
        # DJANGO ADMIN
        # ====================================================
        if resolver and resolver.app_name == "admin" and request.user.is_superuser:
            return None

        # ====================================================
        # APLICACIÓN ACTUAL
        # ====================================================
        current_app = App.get_app_by_request(request)

        app_target = (
            current_app
            if isinstance(current_app, App)
            else session.app
        )

        # ============================================================
        # VALIDACIÓN DE ESCRITURA
        # ============================================================
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            role = getattr(session, "role", None)

            # EXCEPCIONES DE AUTOSERVICIO
            is_partner_registration_create = (
                role
                and getattr(role, "is_partner", False)
                and resolver
                and resolver.app_name == "registrations"
                and resolver.url_name == "create"
                and request.method == "POST"
            )

            if not is_partner_registration_create and app_target:
                user_permission = (
                    UserPermission.objects
                    .filter(
                        user=request.user,
                        app=app_target,
                        role=session.role,
                        is_active=True,
                    )
                    .select_related("permission")
                    .first()
                )

                if not user_permission or user_permission.permission_id != 2:
                    if request.headers.get("X-App-Request") == "true":
                        return JsonResponse({
                            "success": False,
                            "message": "No tienes permisos para modificar en esta aplicación.",
                        }, status=403)

                    messages.error(
                        request,
                        "No tienes permisos para realizar cambios.",
                    )

                    return redirect(getattr(app_target, "url", "core:home"))
            return None

        
        # ============================================================
        # ACTUALIZAR APLICACIÓN ACTIVA
        # ============================================================

        # if request.method == "GET" and current_app and session.app != current_app:
        #     session.app = current_app
        #     session.save(update_fields=["app"])

        if (
            request.method == "GET"
            and isinstance(current_app, App)
            and session.app_id != current_app.pk
        ):
            session.app = current_app
            session.save(update_fields=["app"])

        request.user_session = session

        return None