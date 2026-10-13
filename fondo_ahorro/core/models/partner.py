from django.db import models

from .base import BaseModel
from .person import Person
from .request import Request


# ============================================================
# TIPO DE APORTE
class PartnerContributionType(BaseModel):
    description = models.CharField(verbose_name="Descripción", max_length=255, null=False, blank=False)
    discount_code = models.CharField(verbose_name="Código Descuento", max_length=100, null=True, blank=True)
    state = models.IntegerField(verbose_name="Estado", default=1)
    comment = models.TextField(verbose_name="Observaciones", null=True, blank=True)

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

    state = models.IntegerField(verbose_name="Estado", default=1)

    class Meta:
        db_table = "core_partner"
        verbose_name = "Socio"
        verbose_name_plural = "Socios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id} - {self.person}"
    
    def get_ahorros(self):
        return [
            {
                "id" : contrib.id,
                "contribution_type_id" : contrib.contribution_type.id,
                "description" : contrib.contribution_type.description,
                "comment" : contrib.contribution_type.comment,
                "amount" : contrib.amount 
            }
            for contrib in self.contributions.select_related("contribution_type").all()
        ]


# ============================================================
# DESCUENTO VOLUNTARIO
class PartnerVoluntaryDiscount(BaseModel):
    person = models.ForeignKey(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="partner_voluntary_discounts",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)
    date = models.DateField(verbose_name="Fecha", null=False, blank=False)
    start_date = models.DateField(verbose_name="Fecha Inicio", null=True, blank=True)
    state = models.IntegerField(verbose_name="Estado", default=1)

    class Meta:
        db_table = "core_partner_voluntary_discount"
        verbose_name = "Descuento Voluntario"
        verbose_name_plural = "Descuentos Voluntarios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.person} - {self.amount}"


# ============================================================
# SALDO SOCIO
class PartnerBalance(BaseModel):
    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)
    date = models.DateField(verbose_name="Fecha", null=False, blank=False)

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

    state = models.IntegerField(verbose_name="Estado", default=1)

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
    state = models.IntegerField(verbose_name="Estado", default=1)

    class Meta:
        db_table = "core_partner_reentry"
        verbose_name = "Ingreso de Socio"
        verbose_name_plural = "Ingresos de Socios"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["partner"],
                condition=models.Q(state=1),
                name="unique_active_partner_reentry",
            ),
        ]

    def __str__(self):
        return f"{self.partner} - {self.entry_date}"


# ============================================================
# NUEVO APORTE
class PartnerNewContribution(BaseModel):
    person = models.ForeignKey(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="partner_new_contributions",
        null=False,
        blank=False,
    )

    current_amount = models.DecimalField(
        verbose_name="Monto Actual", max_digits=15, decimal_places=2, null=False, blank=False
    )

    start_month = models.IntegerField(verbose_name="Mes Inicio", null=False, blank=False)

    new_amount = models.DecimalField(
        verbose_name="Nuevo Monto", max_digits=15, decimal_places=2, null=False, blank=False
    )

    fiscal_housing = models.IntegerField(verbose_name="Vivienda Fiscal", null=True, blank=True)
    entry_date = models.DateField(verbose_name="Fecha Ingreso", null=False, blank=False)
    state = models.IntegerField(verbose_name="Estado", default=1)
    equipment_ip = models.GenericIPAddressField(verbose_name="IP Equipo", null=True, blank=True)

    class Meta:
        db_table = "core_partner_new_contribution"
        verbose_name = "Nuevo Aporte"
        verbose_name_plural = "Nuevos Aportes"
        ordering = ["id"]

    def __str__(self):
        return f"{self.person} - {self.current_amount} -> {self.new_amount}"


# ============================================================
# TIPO DE MOVIMIENTO
class PartnerMovementType(BaseModel):
    type = models.CharField(verbose_name="Tipo", max_length=255, null=False, blank=False)
    state = models.IntegerField(verbose_name="Estado", default=1)

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
    date = models.DateField(verbose_name="Fecha", null=False, blank=False)
    state = models.IntegerField(verbose_name="Estado", default=1)

    class Meta:
        db_table = "core_partner_movement"
        verbose_name = "Movimiento de Socio"
        verbose_name_plural = "Movimientos de Socios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.movement_number} - {self.partner} - {self.amount}"
    
# ============================================================
# SOCIO APORTE
class PartnerContribution(BaseModel):
    partner = models.ForeignKey(
        Partner,
        verbose_name="Socio",
        db_column="id_partner",
        on_delete=models.PROTECT,
        related_name="contributions",
        null=False,
        blank=False,
    )

    contribution_type = models.ForeignKey(
        PartnerContributionType,
        verbose_name="Tipo de Aporte",
        db_column="id_contribution_type",
        on_delete=models.PROTECT,
        related_name="contributions",
        null=False,
        blank=False,
    )

    amount = models.DecimalField(verbose_name="Monto", max_digits=15, decimal_places=2, null=False, blank=False)
    
    class Meta:
        db_table = "core_partner_contribution"
        verbose_name = "Aporte de Socio"
        verbose_name_plural = "Aportes de Socios"
        ordering = ["id"]
        unique_together = ("partner", "contribution_type")
        
    
        

# ============================================================
# SOCIO DEPOSITO INCREMENTO AHORRO
class PartnerIncrementDeposit(BaseModel):
    partner = models.ForeignKey(Partner, verbose_name="Socio", db_column="id_partner", on_delete=models.PROTECT, related_name="increment_deposits", null=False, blank=False)
    amount = models.PositiveBigIntegerField(verbose_name="Monto", null=False, blank=False)
    contribution_type = models.ForeignKey(PartnerContributionType, verbose_name="Tipo de Aporte", db_column="id_contribution_type", on_delete=models.PROTECT, related_name="increment_deposits", null=False, blank=False)    
    
    class Meta:
        db_table = "core_partner_increment"
        verbose_name = "Socio Deposito"
        verbose_name_plural = "Socios Depositos"
        ordering = ["id"]
        
    def __str__(self):
        return f"{self.partner} - {self.amount}"
