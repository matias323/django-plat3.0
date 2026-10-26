from django.db import models

from .base import BaseModel
from .person import Person


class EmployeeGrade(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=70, null=False, blank=False)
    code = models.CharField(verbose_name="Código", max_length=50, null=False, blank=False)
    scale = models.CharField(verbose_name="Escalafón", max_length=3, null=False, blank=False)
    scale_type = models.CharField(verbose_name="Tipo Escalafón", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "core_employee_grade"
        verbose_name = "Grado Funcionario"
        verbose_name_plural = "Grados Funcionarios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class EmployeeContractType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)
    code = models.CharField(verbose_name="Código", max_length=50, null=False, blank=False)

    class Meta:
        db_table = "core_employee_contract_type"
        verbose_name = "Tipo de Contrato"
        verbose_name_plural = "Tipos de Contrato"
        ordering = ["id"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class EmployeeSalaryType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)
    code = models.CharField(verbose_name="Código", max_length=50, null=False, blank=False)

    class Meta:
        db_table = "core_employee_salary_type"
        verbose_name = "Tipo de Sueldo"
        verbose_name_plural = "Tipos de Sueldo"
        ordering = ["id"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class EmployeeQualificationType(BaseModel):
    name = models.CharField(verbose_name="Nombre", max_length=255, null=False, blank=False)

    class Meta:
        db_table = "core_employee_qualification_type"
        verbose_name = "Tipo de Calificación"
        verbose_name_plural = "Tipos de Calificación"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Employee(BaseModel):
    code = models.CharField(verbose_name="Código", max_length=50, unique=True, null=False, blank=False)

    person = models.ForeignKey(
        Person,
        verbose_name="Persona",
        db_column="id_person",
        on_delete=models.PROTECT,
        related_name="employees",
        null=False,
        blank=False,
    )

    grade = models.ForeignKey(
        EmployeeGrade,
        verbose_name="Grado",
        db_column="id_grade",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )

    contract_type = models.ForeignKey(
        EmployeeContractType,
        verbose_name="Tipo de Contrato",
        db_column="id_contract_type",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )

    salary_type = models.ForeignKey(
        EmployeeSalaryType,
        verbose_name="Tipo de Sueldo",
        db_column="id_salary_type",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )

    qualification_type = models.ForeignKey(
        EmployeeQualificationType,
        verbose_name="Tipo de Calificación",
        db_column="id_qualification_type",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "core_employee"
        verbose_name = "Funcionario"
        verbose_name_plural = "Funcionarios"
        ordering = ["id"]

    def __str__(self):
        return f"{self.code} - {self.person}"