from django.db import models
from .person import Person
from .session import Permission
from .base import BaseModel

from django.contrib.auth.models import AbstractUser

from core.models.session import Session

from django.utils import timezone

from applications.apps.models import App
from applications.role.models import Role

# AbstractUser ya los trae incluidos con la lógica de hashing y validación.
class User(AbstractUser):
    person = models.OneToOneField(
                            Person, 
                            on_delete=models.CASCADE, 
                            # unique=True,
                            verbose_name="Persona",
                            related_name="persona",
                            # db_column="id"
                            )
    created_at = models.DateTimeField(
        default=timezone.now, verbose_name="Fecha Creación"
    )
    updated_at = models.DateTimeField(
        default=timezone.now, verbose_name="Fecha Modificación"
    )

    def __str__(self):
        return self.person.get_rut() +" - "+self.person.get_full_name()

    def get_password(self):
        return self.password.lower().strip()

    def validate_password(self, password):
        from django.contrib.auth.hashers import check_password
        # 1. Intentar validar usando el verificador seguro de hashes de Django
        if check_password(password, self.password):
            return True
        
        # 2. (Opcional por seguridad/migración) Soporte temporal si queda alguna en texto plano
        if self.password and self.password.lower().strip() == str(password).lower().strip():
            return True
            
        return False
    @classmethod
    def get_active_session(cls,user):
        """Función auxiliar para obtener la sesión activa del usuario."""
        if not user.is_authenticated:
            return None
        return Session.objects.filter(user=user, closed_at=None).first()


    

    class Meta:
        db_table="core_user"

class UserPermission(BaseModel):
    user = models.ForeignKey(
                            User,
                            on_delete=models.PROTECT,
                            verbose_name="Usuario",
                            null=False,
                            blank=False
                            )
    app = models.ForeignKey(
                            App,
                            on_delete=models.PROTECT,
                            verbose_name="App",
                            null=False,
                            blank=False
                            )
    role = models.ForeignKey(
                                Role,
                                on_delete=models.PROTECT,
                                verbose_name="Rol",
                                null=False,
                                blank=False
                                )
    permission = models.ForeignKey(
                                Permission,
                                on_delete=models.PROTECT,
                                verbose_name="Permiso",
                                null=False,
                                blank=False
                                )
    class Meta:
        db_table = "core_user_permission"

    def __str__(self):
        return f"Permiso de usuario {self.user.person.get_full_name()} \n aplicación: {self.app.name} \n rol: {self.role.name} \n permiso: {self.permission.name}"