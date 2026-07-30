from django.db import models

from .base import BaseModel


class PersonType(BaseModel):
    description = models.CharField(
                            verbose_name="Descripcion",
                            max_length=255,
                            null=False,
                            blank=False,
                            )
    state = models.BooleanField(
                            verbose_name="Estado",
                            default=True,
                            null=False,
                            blank=False
                            )

    def __str__(self):
        return self.description

    class Meta:
        db_table="core_person_type"



class Person(BaseModel):
    rut = models.PositiveIntegerField(
                        verbose_name="RUT",
                        # max_length=8,
                        unique=True
                        )
    dv = models.CharField(
                        verbose_name="Digito Verificador",
                        max_length=1
                        )

    first_name = models.CharField(
                        verbose_name="Primer Nombre",
                        max_length=150,
                        blank=False,
                        null=False
                        )
    second_name = models.CharField(
                        verbose_name="Segundo Nombre",
                        max_length=150,
                        null=True
                        )
    last_name_1 = models.CharField(
                        verbose_name="Primer Apellido",
                        max_length=150,
                        null=False
                        )
    last_name_2 = models.CharField(
                        verbose_name="Segundo Apellido",
                        max_length=150,
                        null=True
                        )
    birth_date = models.DateField(
                        verbose_name="Fecha de Nacimiento", 
                        null=False
                        )
    person_type = models.ForeignKey(
                        PersonType,
                        on_delete=models.SET_NULL,
                        verbose_name="Tipo de Persona",
                        null=True,
                        )

    def __str__(self):
        return self.first_name+' '+self.last_name_1 +' '+self.last_name_2 +' -> '+self.person_type.description

    def get_rut(self):
        return str(self.rut)+'-'+self.dv

    def get_full_name(self):
            return self.first_name+' '+self.second_name+' '+self.last_name_1+' '+self.last_name_2

    class Meta:
        db_table="core_person"