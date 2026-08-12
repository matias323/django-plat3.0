from django.shortcuts import redirect
from django.utils.functional import SimpleLazyObject
from django.contrib import messages
from django.http import JsonResponse

from applications.apps.models import App
from core.models.user import User, UserPermission


class ActiveAppSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_session = SimpleLazyObject(lambda: User.get_active_session(request.user))
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None  # Dejar que el login_required de Django gestione la no autenticación

        session = User.get_active_session(request.user)

        if not session:
            if request.headers.get('X-App-Request') == "true":
                return JsonResponse({'success': False, 'message': 'Sesión no válida o expirada.'}, status=401)
            messages.error(request, "Debe iniciar sesión")
            return redirect('core:login')

        current_app = App.get_app_by_request(request)

        # Si no existe la App o no tiene permisos de acceso general
        if not current_app:
            if request.headers.get('X-App-Request') == "true":
                return JsonResponse({'success': False, 'message': 'No tienes permisos para acceder a este recurso.'}, status=403)
            messages.error(request, "No tienes permisos para acceder.")
            return redirect('core:home')

        # Si la app actual es una instancia de App (no un booleano como True en admin/logout)
        app_target = current_app if isinstance(current_app, App) else session.app

        # VALIDACIÓN DE ESCRITURA / MODIFICACIÓN (POST, PUT, PATCH, DELETE)
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            user_permission = UserPermission.objects.filter(
                user=request.user,
                app=app_target,
                role=session.role,
                is_active=True
            ).select_related('permission').first()

            # Si no tiene permiso asignado o su nivel es únicamente 1 (Ver)
            if not user_permission or user_permission.permission_id != 2:
                if request.headers.get('X-App-Request') == "true":
                    return JsonResponse({
                        'success': False, 
                        'message': 'No tienes permisos para modificar en esta aplicación.'
                    }, status=403)
                
                messages.error(request, "No tienes permisos para realizar cambios.")
                return redirect('core:home')

        # Actualizar la app en la sesión si la navegación es normal (GET) y current_app es una App real
        if request.method == 'GET' and isinstance(current_app, App) and session:
            if session.app != current_app:
                session.app = current_app
                session.save(update_fields=['app'])

        return None