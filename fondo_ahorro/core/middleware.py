# core/middleware.py
from django.shortcuts import redirect
from django.utils.functional import SimpleLazyObject
from django.contrib import messages  # Opcional: para mostrar una alerta

from applications.apps.models import App
from core.models import Session 

def get_active_session(user):
    """Función auxiliar para obtener la sesión activa del usuario."""
    if not user.is_authenticated:
        return None
    return Session.objects.filter(user=user, closed_at=None).first()


class ActiveAppSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Adjuntamos el objeto lazy al request para que esté disponible en views/templates
        request.user_session = SimpleLazyObject(lambda: get_active_session(request.user))

        # Continúa el flujo normal si la vista/proceso no fue redirigida por process_view
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Se ejecuta DESPUÉS de que Django resolvió la URL (request.resolver_match ya existe)
        pero ANTES de ejecutar la vista.
        """
        # if not request.user.is_authenticated and request.resolver_match.url_name != 'registration' :
        #     return redirect('core:login')

        # if request.resolver_match.url_name == 'registration':
        #     return None

        if request.user.is_authenticated:
            current_app = App.get_app_by_request(request)

            if not current_app:
                messages.error(request, f"No tienes permisos para acceder.")
                # REDIRIGIR A OTRA APP (Ej: Dashboard principal o App por defecto)
                # Asegúrate de evitar un bucle infinito de redirecciones si la vista destino también usa este chequeo!
                return redirect('core:home') 

            # 2. SI TIENE PERMISO: Actualizar la sesión activa
            session = get_active_session(request.user)

            if str(type(current_app)) != "<class 'bool'>" and session  :
                session.app = current_app 
                session.save(update_fields=['app'])

            
        # Si retorna None, Django continúa ejecutando la vista normalmente
        return None