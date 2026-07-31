from applications.apps.models import App

def navigation_menu(request):
    """ Inyecta de forma global el menú de aplicaciones en todos los templates """
    context = {'navbar_apps': []}
    
    if request.user.is_authenticated:
        # Resolvemos el filtro de sesión activa de manera segura sin causar excepciones
        # Asumiendo que 'Session' guarda el rol activo del usuario
        # from django.contrib.sessions.models import Session as DjangoSession # Cambia a tu modelo real
        # Suponiendo que tu modelo propio se llama 'UserSession' o similar:
        # session = YourSessionModel.objects.filter(user=request.user, closed_at__isnull=True).first()
        
        # Simulación basada en tu código (ajusta la importación de tu modelo Session aquí):
        from core.models import Session as UserSession
        session = UserSession.objects.filter(user=request.user, closed_at=None).first()

        if session and session.role:
            # Llamamos al método optimizado del modelo App
            context['navbar_apps'] = App.get_navbar_menu(request.user, session.role)
            
    return context

