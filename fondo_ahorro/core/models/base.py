from django.db import models

from django.conf import settings

from django.utils import timezone


class BaseModel(models.Model):
    created_at = models.DateTimeField(
        verbose_name="Fecha Creación",
        default=timezone.now(),
    )
    updated_at = models.DateTimeField(
        verbose_name="Fecha Modificación",
        default=timezone.now(),
    )
    user_create = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # O models.SET_NULL (si null=True)
        verbose_name="Usuario Creador",
        related_name="%(class)s_created",  # Evita colisiones de nombres entre hijos
        null=True,
        default= 1,
    )
    user_update = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Usuario Modificador",
        related_name="%(class)s_updated",  # Evita colisiones de nombres entre hijos
        null=True,
        default= 1,
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Es Activo",
    )
    class Meta:
        abstract = True
        ordering = ["-created_at"]


