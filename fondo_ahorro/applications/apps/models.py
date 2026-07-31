from django.db import models

from core.models.base import BaseModel


# Create your models here.



class App(BaseModel):
    name = models.CharField(
                            verbose_name="Nombre de Aplicación",
                            max_length=255,
                            blank=False,
                            null=False,
                            )
    url = models.CharField(
                            verbose_name="URL de Aplicación",
                            max_length=255,
                            blank=False,
                            null=False,
                            )
    has_daughter = models.BooleanField(
                                    verbose_name="Tiene Hijas ?",
                                    default=False,
                                    null=False,
                                    blank=False,
                                    )
    order = models.IntegerField(
                                verbose_name="Orden",
                                null=False,
                                default=1,
                                blank=False,
                                )
    father_app = models.ForeignKey(
                                "self",
                                on_delete=models.SET_NULL,
                                null=True,
                                verbose_name="Aplicación Padre",
                                related_name="sub_apps",
                                blank=True,
                                )
    class Meta:
        db_table = "core_app"
        verbose_name = "Aplicación"
        verbose_name_plural = "Aplicaciones"

    def __str__(self):
        if self.father_app:
            return f"{self.name}  | App Padre: {self.father_app.name}"
        return self.name

    def get_apps_hijas(self):
        return self.father_app.sub_apps.all()

    
    