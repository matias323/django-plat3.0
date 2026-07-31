
from django.db import models

from django.conf import settings

from .base import BaseModel

from applications.apps.models import App
from applications.role.models import Role, Permission



class Session(BaseModel):
    closed_at = models.DateTimeField(
                                    verbose_name="Fecha Término",
                                    null=True,
                                    blank=True,
                                    )
    app = models.ForeignKey(
                            App,
                            on_delete=models.PROTECT,
                            verbose_name="App Actual",
                            null=False,
                            blank=False
                            )
    user = models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            on_delete=models.PROTECT,
                            verbose_name="Usuario",
                            null=False,
                            blank=False,
                            )
    role = models.ForeignKey(
                            Role,
                            on_delete=models.PROTECT,
                            verbose_name="Rol Actual",
                            null=False,
                            blank=False,
                            )
    permission = models.ForeignKey(
                                Permission,
                                on_delete=models.PROTECT,
                                verbose_name="Permiso Actual",
                                null=False,
                                blank=False,
                                )
    class Meta:
        db_table= "core_session"

    def __str__(self):
        return f"Sesión {self.status()} usuario {self.user.person.get_full_name()} \n aplicación: {self.app.name} \n rol: {self.role.name} \n permiso: {self.permission.name}"

    def status(self):
        if self.is_active and self.closed_at is None:
            return "Activa"
        return "Terminada"
