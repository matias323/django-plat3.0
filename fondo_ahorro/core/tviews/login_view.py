from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from core.models.user import User, UserPermission
from core.models.session import Session


from core.forms.loginForm import LoginForm

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