from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models.base import BaseModel
from .utils import get_month_name


# Create your models here.
class PeriodoContable(BaseModel):
    def __str__(self):
        return f"{self.year}-{self.month:02d}"
    
    year = models.PositiveIntegerField(verbose_name="Año", null=False, blank=False)
    month = models.PositiveSmallIntegerField(
        verbose_name="Mes", 
        validators=[MinValueValidator(1), MaxValueValidator(12)], 
        null=False, 
        blank=False
    )
    start_date = models.DateField(verbose_name="Fecha Inicio", null=False, blank=False)
    end_date = models.DateField(verbose_name="Fecha Termino", null=False, blank=False)
    opening_date = models.DateField(verbose_name="Fecha Apertura", null=True, blank=True)
    closing_date = models.DateField(verbose_name="Fecha Cierre", null=True, blank=True)
    
    class Meta:
        db_table = "contab_periodo"
        verbose_name = "Periodo Contable"
        verbose_name_plural = "Periodos Contables"
        ordering = ["-year", "-month"]
        # restriccion para que exista solo 1 periodo por anio y mes
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="unique_periodo_anio_mes"),
        ]
        
    def periodo_to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            "year": self.year,
            "month": self.month,
            "month_name": get_month_name(self.month),
            "start_date": self.start_date,
            "end_date": self.end_date if self.end_date else None,
            "opening_date": self.opening_date,
            "closing_date": self.closing_date if self.closing_date else None,
            "user_create": self.user_create.person.get_name(),
            "user_update": self.user_update.person.get_name() if self.user_update else None
        }