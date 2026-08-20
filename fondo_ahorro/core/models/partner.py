from django.db import models

from .base import BaseModel
from .person import Person
from .request import Request


# ============================================================
# TIPO DE APORTE
class PartnerContributionType(BaseModel):
    description = models.CharField(verbose_name="Descripción", max_length=255, null=False, blank=False)
    discount_code = models.CharField(verbose_name="Código Descuento", max_length=100, null=True, blank=True)

    class Meta:
        db_table = "core_partner_contribution_type"
        verbose_name = "Tipo de Aporte"
        verbose_name_plural = "Tipos de Aporte"
        ordering = ["id"]

    def __str__(self):
        return self.description


# ============================================================
# SOCIO
# Una persona solamente puede tener un registro Partner.
# state = 1 -> socio activo
# state = 0 -> socio inactivo

class Partner(BaseModel):
    person = models.OneToOneField(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="partner",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "core_partner"
        verbose_name = "Socio"
        verbose_name_plural = "Socios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id} - {self.person}"


# ============================================================
# DESCUENTO VOLUNTARIO
class PartnerVoluntaryDiscount(BaseModel):
    partner = models.ForeignKey(
        Partner,
        verbose_name="Socio",
        db_column="id_partner",
        on_delete=models.PROTECT,
        related_name="partner_voluntary_discounts",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)
    start_date = models.DateField(verbose_name="Fecha Inicio", null=True, blank=True)

    class Meta:
        db_table = "core_partner_voluntary_discount"
        verbose_name = "Descuento Voluntario"
        verbose_name_plural = "Descuentos Voluntarios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.partner} - {self.amount}"


# ============================================================
# SALDO SOCIO
class PartnerBalance(BaseModel):
    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)

    contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Tipo de Aporte",
        db_column="id_contribution_type",
        on_delete=models.PROTECT,
        related_name="balances",
        null=False,
        blank=False,
    )

    partner = models.ForeignKey(
        Partner,
        verbose_name="Socio",
        db_column="id_partner",
        on_delete=models.PROTECT,
        related_name="balances",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "core_partner_balance"
        verbose_name = "Saldo de Socio"
        verbose_name_plural = "Saldos de Socios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.partner} - {self.contribution_type} - {self.amount}"


# ============================================================
# INGRESO / REINGRESO DEL SOCIO
#
# Cada vez que una persona entra como socio se crea un registro:
#
# Primer ingreso:
#   PartnerReentry #1 state=1
#
# Renuncia:
#   PartnerReentry #1 state=0
#
# Reingreso:
#   PartnerReentry #2 state=1

class PartnerReentry(BaseModel):
    partner = models.ForeignKey(
        Partner,
        verbose_name="Socio",
        db_column="id_partner",
        on_delete=models.PROTECT,
        related_name="reentries",
        null=False,
        blank=False,
    )

    request = models.OneToOneField(
        Request,
        verbose_name="Solicitud",
        db_column="id_request",
        on_delete=models.PROTECT,
        related_name="partner_reentry",
        null=False,
        blank=False,
    )

    entry_date = models.DateField(verbose_name="Fecha Ingreso", null=False, blank=False)
    resignation_date = models.DateField(verbose_name="Fecha Renuncia", null=True, blank=True)

    class Meta:
        db_table = "core_partner_reentry"
        verbose_name = "Ingreso de Socio"
        verbose_name_plural = "Ingresos de Socios"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["partner"],
                condition=models.Q(is_active=True),
                name="unique_active_partner_reentry",
            ),
        ]

    def __str__(self):
        return f"{self.partner} - {self.entry_date}"
    

# ============================================================
# TIPO DE MOVIMIENTO
class PartnerMovementType(BaseModel):
    name = models.CharField(verbose_name="Tipo", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "core_partner_movement_type"
        verbose_name = "Tipo de Movimiento"
        verbose_name_plural = "Tipos de Movimiento"
        ordering = ["id"]

    def __str__(self):
        return self.type


# ============================================================
# MOVIMIENTO SOCIO
class PartnerMovement(BaseModel):
    movement_type = models.ForeignKey(
        PartnerMovementType,
        verbose_name="Tipo de Movimiento",
        db_column="id_movement_type",
        on_delete=models.PROTECT,
        related_name="movements",
        null=False,
        blank=False,
    )

    partner = models.ForeignKey(
        Partner,
        verbose_name="Socio",
        db_column="id_partner",
        on_delete=models.PROTECT,
        related_name="movements",
        null=False,
        blank=False,
    )

    contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Tipo de Aporte",
        db_column="id_contribution_type",
        on_delete=models.PROTECT,
        related_name="movements",
        null=False,
        blank=False,
    )

    movement_number = models.IntegerField(verbose_name="Número Movimiento", null=False, blank=False)
    description = models.CharField(verbose_name="Descripción", max_length=255, null=True, blank=True)
    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)

    class Meta:
        db_table = "core_partner_movement"
        verbose_name = "Movimiento de Socio"
        verbose_name_plural = "Movimientos de Socios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.movement_number} - {self.partner} - {self.amount}"


# ============================================================
# APORTE SOCIO
class PartnerContribution(BaseModel):
    contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Tipo de Aporte",
        db_column="id_contribution_type",
        on_delete=models.PROTECT,
        related_name="partner_contributions",
        null=False,
        blank=False,
    )

    partner = models.ForeignKey(
        Partner,
        verbose_name="Socio",
        db_column="id_partner",
        on_delete=models.PROTECT,
        related_name="contributions",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(
        verbose_name="Monto",
        max_digits=15,
        decimal_places=2,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "core_partner_contribution"
        verbose_name = "Aporte de Socio"
        verbose_name_plural = "Aportes de Socios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.partner} - {self.contribution_type} - {self.amount}"