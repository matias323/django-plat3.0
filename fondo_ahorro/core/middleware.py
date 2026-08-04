# core/middleware.py
from django.utils.functional import SimpleLazyObject

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
        # 1. Procesar la petición primero para que Django resuelva la vista y request.resolver_match
        response = self.get_response(request)

        # 2. Solo actualizar si el usuario está autenticado
        if request.user.is_authenticated:
            current_app = App.get_app_by_request(request)
            
            if current_app:
                # Buscar la sesión activa del usuario y actualizar la app actual
                session = get_active_session(request.user)
                if(session):
                    session.app = current_app 
                    session.save(update_fields=['app'])
        # Usamos SimpleLazyObject para que la consulta a la BDD SOLO se ejecute
        # si realmente accedes a request.user_session en tu vista/template.
        request.user_session = SimpleLazyObject(lambda: get_active_session(request.user))

        response = self.get_response(request)

        return response

# class CustomSessionMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):

#         request.user_session = SimpleLazyObject(lambda: get_active_session(request.user))

#         response = self.get_response(request)
#         return response