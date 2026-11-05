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

    def save(self, *args, **kwargs):
        # Extraemos el usuario de auditoría si viene en kwargs (igual que en BaseModel y RoleApp)
        user_audit = kwargs.pop('user', None)
        
        is_new = self.pk is None
        
        # Obtenemos el estado anterior si ya existía en la base de datos (para detectar si pasó de inactivo a activo)
        old_is_active = False
        if not is_new:
            old_is_active = RoleUser.objects.filter(pk=self.pk).values_list('is_active', flat=True).first()

        # Guardamos el registro usando el save del BaseModel (que maneja user_create y user_update)
        # Nota: pasamos user_audit de vuelta en kwargs si BaseModel lo espera, o llamamos super().save() limpio
        super().save(*args, user=user_audit, **kwargs)

        # Si es un nuevo registro activo, o si acaba de ser activado (is_active pasó de False a True)
        if (is_new and self.is_active) or (not is_new and not old_is_active and self.is_active):
            self._crear_permisos_usuario(user_audit)

    def _crear_permisos_usuario(self, user_audit):
        """Método auxiliar para registrar UserPermission para todas las apps del rol recién asignado."""
        from applications.role.models import RoleApp, Permission
        from core.models.user import UserPermission

        # Buscamos el permiso por defecto (igual que en RoleApp)
        permiso_default = Permission.objects.filter(id=1).first()
        if not permiso_default:
            permiso_default = Permission.objects.first()

        if not permiso_default:
            return 

        # Obtenemos todas las aplicaciones asociadas a este rol a través de RoleApp
        role_apps = RoleApp.objects.filter(role=self.role, is_active=True).select_related('app')

        # Creamos o aseguramos el UserPermission para cada app de este rol y usuario
        for ra in role_apps:
            UserPermission.objects.get_or_create(
                user=self.user,
                app=ra.app,
                role=self.role,
                defaults={
                    'permission': permiso_default,
                    'is_active': True,
                    'user_create': user_audit,
                    'user_update': user_audit,
                }
            )
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
        db_table = "core_role_app"
        unique_together = ('role', 'app') 

    def __str__(self):
        return f"{self.role.name} - {self.app.name}"

    def save(self, *args, **kwargs):
        user_audit = kwargs.get('user', None)
        
        is_new = self.pk is None
        
        super().save(*args, **kwargs)

        if is_new and self.is_active:
            self._crear_permisos_masivos(user_audit)

    def _crear_permisos_masivos(self, user_audit):
        """Método auxiliar para registrar UserPermission masivamente a los usuarios del rol"""
        from applications.role.models import RoleUser, Permission
        from core.models.user import UserPermission

        permiso_default = Permission.objects.filter(id=1).first()
        if not permiso_default:
            permiso_default = Permission.objects.first()

        if not permiso_default:
            return 

        usuarios_con_rol = RoleUser.objects.filter(
            role=self.role, 
            is_active=True
        ).select_related('user')

        # Creamos o aseguramos el UserPermission para cada usuario en esta app
        for ru in usuarios_con_rol:
            UserPermission.objects.get_or_create(
                user=ru.user,
                app=self.app,
                role=self.role,
                defaults={
                    'permission': permiso_default,
                    'is_active': True,
                    'user_create': user_audit,
                    'user_update': user_audit,
                }
            )


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