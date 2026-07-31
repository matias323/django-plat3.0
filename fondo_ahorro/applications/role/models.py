from django.db import models

from core.models.base import BaseModel
# from core.models.user import User
from django.conf import settings

from applications.apps.models import App
# Create your models here.


class Role(BaseModel):

    name = models.CharField(
                            verbose_name="Descripción",
                            max_length=255,
                            null=False,
                            blank=False,
                            )
    is_unique = models.BooleanField(
                            default=False,
                            verbose_name="Es unico",
                            )
    is_partner = models.BooleanField(
                                default=False,
                                verbose_name="Es socio",
                                )

    class Meta:
        db_table = "core_role"

    def __str__(self):
        return f"{self.name}"


class RoleUser(BaseModel):
    role = models.ForeignKey(
                            Role,
                            on_delete=models.PROTECT,
                            verbose_name="Rol",
                            )
    user = models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            on_delete=models.PROTECT,
                            verbose_name="Usuario",
                            )
    class Meta:
        db_table = "core_role_user"

    def __str__(self):
        return f"{self.role.name} - {self.user.person.get_full_name()}"

class RoleApp(BaseModel):
    role = models.ForeignKey(
                            Role,
                            on_delete=models.PROTECT,
                            verbose_name="Rol",
                            )
    app = models.ForeignKey(
                            App,
                            on_delete=models.PROTECT,
                            verbose_name="Aplicación",
                            )
    class Meta:
        db_table="core_role_app"
        


    def __str__(self):
        return f"{self.role.name} - {self.app.name}"


class Permission(BaseModel):
    name = models.CharField(
                        verbose_name="Nombre Permiso",
                        null=False,
                        blank=False,
                        )
    class Meta:
        db_table="core_permission"

    def __str__(self):
        return f"{self.name}"