from django.views.generic import TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from core.models.user import User, UserPermission
from core.models.session import Session

from datetime import datetime


from core.forms.loginForm import LoginForm

from core.models.session import Session
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib.auth.views import LogoutView

class LogoutView(LogoutView):
    def post(self, request, *args, **kwargs):

        if request.user.is_authenticated:
            Session.objects.filter(user=request.user, closed_at=None).update(
                closed_at = datetime.now()
            )
        
        return super().post(request, *args, **kwargs)


# 

class SessionView(LoginRequiredMixin, ListView):
    model = Session
    template_name = 'core/session_list.html'
    context_object_name = 'Sessions'
    paginate_by = 15 

    def get_queryset(self):
        return Session.objects.all().order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Listado de Sesiones"
        return context

    def post(self, request, *args, **kwargs):
        session_id = request.POST.get('session_id')
        
        if session_id:
            # Buscamos la sesión o devolvemos 404 si no existe
            session = get_object_or_404(Session, id=session_id)
            
            session.is_active = False
            session.closed_at = datetime.now()
            session.save()
            
            messages.success(request, f"La sesión #{session.id} ha sido finalizada correctamente.")
        
        return redirect('core:session')

class LoginView(TemplateView):
    template_name = 'core/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = LoginForm()
        return context

    def post(self, request,*args,**kwargs):
        form = LoginForm( data=request.POST)

        if form.is_valid():
            rut = form.cleaned_data.get("rut")
            password = form.cleaned_data.get("password")

            rut_limpio = rut.strip().replace(".", "").replace("-", "").upper()

            try:
                user = User.objects.get(
                    person__rut__iexact=rut_limpio[:-1],
                    person__dv__iexact=rut_limpio[-1:], 
                    is_active=True
                    )
            except User.DoesNotExist:
                messages.error(request, "Usuario no existe con rut ("+rut+")")
                return self.render_to_response({"form": form})
            
            if user :
                if not user.validate_password(password):
                    messages.error(
                        request, "RUT o Contraseña no coinciden."
                    )
                    return self.render_to_response({"form": form})

                if not user.is_active:
                    messages.error(
                        request, "Esta cuenta de usuario está desactivada."
                    )
                    return self.render_to_response({"form": form})

                usr_permission = UserPermission.objects.filter(user=user).first()
                session = Session.objects.get_or_create(
                    closed_at = None, 
                    user=user, 
                    app=usr_permission.app, 
                    role= usr_permission.role, 
                    permission = usr_permission.permission
                )
                
                login(request, user)

                request.user_session = session


                return redirect("core:home")
            else:
                messages.error(request, "Usuario no existe con RUT indicado.("+rut+")")
        else:
            messages.error(
                request, "Por favor corrige los errores del formulario."
            )

        return self.render_to_response({"form": form})