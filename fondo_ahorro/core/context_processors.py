from applications.apps.models import App

def navigation_menu(request):
    """ Inyecta de forma global el menú de aplicaciones en todos los templates """
    context = {'navbar_apps': []}
    
    if request.user.is_authenticated:
        from core.models import Session as UserSession
        session = UserSession.objects.filter(user=request.user, closed_at=None).first()

        if session and session.role:
            # Llamamos al método optimizado del modelo App
            context['navbar_apps'] = App.get_navbar_menu(request.user, session.role)
            
    return context

