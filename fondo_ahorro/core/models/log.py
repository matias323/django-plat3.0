from django.conf import settings
from django.db import models


class LogModel(models.Model):
    ACCION_CHOICES = (
        ("CREATE", "Creacion"),
        ("UPDATE", "Actualizacion"),
        ("DELETE", "Eliminacion"),
    )
    
    table_name = models.CharField(max_length=100)
    record_id = models.IntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACCION_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    previous_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "core_log"
        verbose_name = "Log"
        verbose_name_plural = "Logs"
        ordering = ["-creation_date"]