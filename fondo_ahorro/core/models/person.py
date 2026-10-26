from django.db import models

from .base import BaseModel
from .location import Commune
from .document import Document
from .bank import Banco, BancoCuentaTipo


class PersonType(BaseModel):
    description = models.CharField(
                            verbose_name="Descripcion",
                            max_length=255,
                            null=False,
                            blank=False,
                            )
    # state = models.BooleanField(
    #                         verbose_name="Estado",
    #                         default=True,
    #                         null=True,
    #                         blank=True
    #                         )

    def __str__(self):
        return f"{self.id} - {self.description}"

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
        if not self.rut:
            return ""
        
        try:
            # 3. Formatear el cuerpo con puntos de miles usando formato numérico
            cuerpo_formateado = f"{int(self.rut):,}".replace(",", ".")
            return f"{cuerpo_formateado}-{self.dv}"
        except ValueError:
            # Retorna el valor original limpio si el cuerpo no es numérico
            return str(self.rut)+self.dv

    def get_full_name(self):
            return self.first_name+' '+self.second_name+' '+self.last_name_1+' '+self.last_name_2

    def get_name(self):
         return f" {self.first_name} {self.last_name_1} {self.last_name_2}"


    class Meta:
        db_table="core_person"


# ============================================================
# PERSONA CONTACTO TIPO
class PersonContactType(BaseModel):
    name = models.CharField(
        verbose_name="Nombre",
        max_length=100,
        unique=True,
        null=False,
        blank=False,
    )

    state = models.IntegerField(
        verbose_name="Estado",
        default=1,
    )

    class Meta:
        db_table = "core_person_contact_type"
        verbose_name = "Tipo de Contacto"
        verbose_name_plural = "Tipos de Contacto"
        ordering = ["id"]

    def __str__(self):
        return self.name


# ============================================================
# PERSONA CONTACTO
class PersonContact(BaseModel):
    person = models.ForeignKey(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="contacts",
        null=False,
        blank=False,
    )

    contact_type = models.ForeignKey(
        PersonContactType,
        verbose_name="Tipo de Contacto",
        db_column="id_contact_type",
        on_delete=models.PROTECT,
        related_name="contacts",
        null=False,
        blank=False,
    )

    value = models.CharField(
        verbose_name="Valor",
        max_length=255,
        null=False,
        blank=False,
    )

    state = models.IntegerField(
        verbose_name="Estado",
        default=1,
    )

    class Meta:
        db_table = "core_person_contact"
        verbose_name = "Contacto de Persona"
        verbose_name_plural = "Contactos de Personas"
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=["person", "contact_type"],
                condition=models.Q(state=1),
                name="unique_active_person_contact_type",
            ),
        ]

    def __str__(self):
        return f"{self.person} - {self.contact_type}: {self.value}"


# ============================================================
# PERSONA DIRECCIÓN
class PersonAddress(BaseModel):
    person = models.ForeignKey(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="addresses",
        null=False,
        blank=False,
    )

    commune = models.ForeignKey(
        Commune,
        verbose_name="Comuna",
        db_column="id_commune",
        on_delete=models.PROTECT,
        related_name="person_addresses",
        null=False,
        blank=False,
    )

    address = models.CharField(
        verbose_name="Dirección",
        max_length=255,
        null=False,
        blank=False,
    )

    number = models.CharField(
        verbose_name="Número",
        max_length=30,
        null=False,
        blank=False,
    )

    state = models.IntegerField(
        verbose_name="Estado",
        default=1,
    )

    class Meta:
        db_table = "core_person_address"
        verbose_name = "Dirección de Persona"
        verbose_name_plural = "Direcciones de Personas"
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=["person"],
                condition=models.Q(state=1),
                name="unique_active_person_address",
            ),
        ]

    def __str__(self):
        return f"{self.address} {self.number}, {self.commune.name}"


# ============================================================
# PERSONA CODIGO DIPRECA
class PersonDiprecaCode(BaseModel):
    person = models.ForeignKey(
        Person,
        verbose_name="Person",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="loan_dipreca_codes",
        null=False,
        blank=False,
    )

    document = models.ForeignKey(
        Document,
        verbose_name="Document",
        db_column="id_document",
        on_delete=models.PROTECT,
        related_name="loan_dipreca_codes",
        null=False,
        blank=False,
    )

    dipreca_code = models.BigIntegerField(verbose_name="DIPRECA Code", null=False, blank=False)

    class Meta:
        db_table = "loan_dipreca_code"
        verbose_name = "Persona Codigo DIPRECA"
        verbose_name_plural = "Persona Codigo DIPRECA"
        ordering = ["id"]

    def __str__(self):
        return f"{self.person} - {self.dipreca_code}"


# ============================================================
# PERSONA BANCO
class PersonaBanco(BaseModel):

    banco = models.ForeignKey(
        'core.Banco',
        verbose_name="Banco",
        db_column="id_banco",
        on_delete=models.PROTECT,
        related_name="cuentas_personas",
        null=True,
        blank=True,
    )

    cuenta_tipo = models.ForeignKey(
        'core.BancoCuentaTipo',
        verbose_name="Tipo de Cuenta Bancaria",
        db_column="id_cuenta_tipo",
        on_delete=models.PROTECT,
        related_name="cuentas_personas",
        null=True,
        blank=True,
    )

    n_cuenta = models.CharField(
        verbose_name="Número de Cuenta",
        max_length=50,
        null=True,
        blank=True,
    )

    persona = models.ForeignKey(
        'core.Person',
        verbose_name="Persona",
        db_column="id_persona",
        on_delete=models.PROTECT,
        related_name="cuentas_bancarias",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "persona_banco"
        verbose_name = "Cuenta Bancaria de Persona"
        verbose_name_plural = "Cuentas Bancarias de Personas"
        ordering = ["persona", "banco"]

    def __str__(self):
        return f"{self.persona} - {self.banco} - {self.n_cuenta}"