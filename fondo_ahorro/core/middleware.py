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
            lambda: User.get_active_session(request.user)
        )

        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        resolver = request.resolver_match

        # ====================================================
        # RUTAS QUE NO DEBEN VALIDAR LA SESIÓN DE APLICACIÓN
        # if resolver and resolver.app_name == "core" and resolver.url_name in {

        if resolver  and resolver.url_name in {

            "login",
            "logout",
            "register",
            "perfil",

        }:
            return None


        session = User.get_active_session(request.user)
                
        if not session:

            logout(request)

            messages.error(
                request,
                "Tu sesión expiró. Debes iniciar sesión nuevamente.",
            )

            return redirect("core:login")



        # ====================================================
        # USUARIO NO AUTENTICADO
        if not request.user.is_authenticated:
            # logout(request)
            
            # messages.error(
            #     request,
            #     "Tu sesión expiró. Debes iniciar sesión nuevamente.",
            # )

            # return redirect("core:login") ???
            return None

        # ====================================================
        # SUPERUSUARIO
        if request.user.is_superuser:
            return None

        # ====================================================
        # DJANGO ADMIN
        if resolver and resolver.app_name == "admin":
            return None

        # ====================================================
        # SESIÓN ACTIVA DEL SISTEMA (Esto da error cuando nunca a tenido session xdd usuario nuevo... )
        session = User.get_active_session(request.user)

        if not session:
            if request.headers.get("X-App-Request") == "true":
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Sesión no válida o expirada.",
                    },
                    status=401,
                )

            # El usuario sigue autenticado en Django pero su
            # sesión interna ya no existe. Cerramos la sesión
            # Django para evitar el bucle /login/ -> /login/.
            logout(request)

            messages.error(
                request,
                "Tu sesión expiró. Debes iniciar sesión nuevamente.",
            )

            return redirect("core:login")

        # ====================================================
        # APLICACIÓN ACTUAL
        current_app = App.get_app_by_request(request)

        if not current_app:
            if request.headers.get("X-App-Request") == "true":
                return JsonResponse(
                    {
                        "success": False,
                        "message": "No tienes permisos para acceder a este recurso.",
                    },
                    status=403,
                )

            messages.error(
                request,
                "No tienes permisos para acceder.",
            )

            return redirect("core:home")

        app_target = (
            current_app
            if isinstance(current_app, App)
            else session.app
        )

        # ============================================================
        # VALIDACIÓN DE ESCRITURA
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            resolver = request.resolver_match
            role = getattr(session, "role", None)

            # ============================================================
            # EXCEPCIONES DE AUTOSERVICIO
            is_partner_registration_create = (
                role
                and getattr(role, "is_partner", False)
                and resolver
                and resolver.app_name == "registrations"
                and resolver.url_name == "create"
                and request.method == "POST"
            )

            if not is_partner_registration_create:
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

                    return redirect("core:home")

        # ====================================================
        # ACTUALIZAR APP ACTIVA
        if (
            request.method == "GET"
            and isinstance(current_app, App)
            and session
            # and session.app != current_app
        ):
            session.app = current_app
            session.save(update_fields=["app"])



        # para saber el rol en el html creamos el user_session en la request-
        #entonces ahora en el html podemos hacer {{request.user_sesison.role.name}} -> "Desarrollo".

        request.user_session = session

        return None