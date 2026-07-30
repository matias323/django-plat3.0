from django.db import models
from .person import Person

from .base import BaseModel

from django.contrib.auth.models import AbstractUser

from django.utils import timezone

# class UserType(models.Model):
#     description = models.CharField(
#                             verbose_name="Descripcion",
#                             max_length=255,
#                             null=False,
#                             blank=False,
#                             )
#     state = models.BooleanField(
#                             verbose_name="Estado",
#                             default=True,
#                             null=False,
#                             blank=False
#                             )

#     def __str__(self):
#         return self.description

#     class Meta:
#         db_table="core_user_type"



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
    # username = models.CharField(
    #                         max_length=50, 
    #                         verbose_name="Nombre de Usuario",
    #                         unique=True
    #                         )
    # password = models.CharField(
    #                         verbose_name="Contraseña",
    #                         max_length=150,
    #                         )
    # email = models.EmailField(
    #                         verbose_name="Correo",
    #                         unique=True, 
    #                         max_length=255, 
    #                         null=False, 
    #                         blank=False
    #                         )
    # user_type = models.ForeignKey(
    #                         UserType,
    #                         verbose_name="Tipo de Usuario", 
    #                         on_delete=models.SET_NULL,
    #                         null=True,
    #                         related_name="tipo_usuario",
    #                         )
    created_at = models.DateTimeField(
        default=timezone.now(), verbose_name="Fecha Creación"
    )
    updated_at = models.DateTimeField(
        default=timezone.now(), verbose_name="Fecha Modificación"
    )

    def __str__(self):
        return self.username +" - "+self.person.get_full_name()

    def get_password(self):
        return self.password.lower().strip()

    def validate_password(self, password):
        return self.get_password() == str(password).lower().strip()

    class Meta:
        db_table="core_user"
