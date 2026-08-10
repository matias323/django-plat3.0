from django.db import models
from django.conf import settings


class Observation(models.Model):
    comment = models.TextField(
        null=True,
        blank=True
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_user"
    )

    date = models.DateField(
        null=True,
        blank=True
    )

    time = models.TimeField(
        null=True,
        blank=True
    )

    ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = "core_observation"

    def __str__(self):
        return f"Observation {self.id}"