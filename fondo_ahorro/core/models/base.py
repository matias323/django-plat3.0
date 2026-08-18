from django.db import models
from django.conf import settings
from django.utils import timezone





class BaseModel(models.Model):
    created_at = models.DateTimeField(
        verbose_name="Fecha Creación",
        default=timezone.now,
    )
    updated_at = models.DateTimeField(
        verbose_name="Fecha Modificación",
        default=timezone.now,
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

    def save(self, *args, **kwargs):
        # 1. Extraemos el usuario si lo pasaron en los kwargs
        # Usamos pop() para quitarlo de kwargs, ya que super().save() no acepta el argumento 'user'
        user = kwargs.pop('user', None)

        if user and user.is_authenticated:
            # self.pk es None cuando el objeto es nuevo (aún no se guarda en BD)
            if not self.pk:
                self.user_create = user
            
            # Siempre actualizamos el usuario modificador
            self.user_update = user
            self.updated_at = timezone.now()

        # 2. Llamamos al método save() original de models.Model
        super().save(*args, **kwargs)

