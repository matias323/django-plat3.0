
from django.db import models
from core.models.base import BaseModel


# ============================================================
# BANCO
# ============================================================
class Banco(BaseModel):
    nombre = models.CharField(
        verbose_name="Nombre",
        max_length=50,
        null=False,
        blank=False,
    )

    codigo_banco = models.CharField(
        verbose_name="Código Banco",
        max_length=10,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "banco"
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo_banco} - {self.nombre}"


# ============================================================
# CUENTA BANCARIA
# ============================================================
class BancoCuenta(BaseModel):
    descripcion = models.CharField(
        verbose_name="Descripción",
        max_length=50,
        null=False,
        blank=False,
    )

    codigo_cuenta = models.CharField(
        verbose_name="Código Cuenta",
        max_length=10,
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "banco_cuenta"
        verbose_name = "Cuenta Bancaria"
        verbose_name_plural = "Cuentas Bancarias"
        ordering = ["descripcion"]

    def __str__(self):
        return f"{self.codigo_cuenta} - {self.descripcion}"


# ============================================================
# TIPO DE CUENTA BANCARIA POR BANCO
# ============================================================
class BancoCuentaTipo(BaseModel):
    banco = models.ForeignKey(
        Banco,
        verbose_name="Banco",
        db_column="id_banco",
        on_delete=models.PROTECT,
        related_name="tipos_cuenta",
        null=False,
        blank=False,
    )

    banco_cuenta = models.ForeignKey(
        BancoCuenta,
        verbose_name="Cuenta Bancaria",
        db_column="id_banco_cuenta",
        on_delete=models.PROTECT,
        related_name="bancos",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "banco_cuenta_tipo"
        verbose_name = "Tipo de Cuenta por Banco"
        verbose_name_plural = "Tipos de Cuenta por Banco"
        ordering = ["banco", "banco_cuenta"]

        constraints = [
            models.UniqueConstraint(
                fields=["banco", "banco_cuenta"],
                name="unique_banco_cuenta_tipo",
            ),
        ]

    def __str__(self):
        return (
            f"{self.banco.nombre} - "
            f"{self.banco_cuenta.descripcion}"
        )
