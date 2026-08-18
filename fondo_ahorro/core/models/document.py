from django.db import models
from django.conf import settings
from .base import BaseModel


class DocumentType(BaseModel):
    type = models.CharField(
        max_length=100
    )

    state = models.IntegerField(
        default=1
    )

    class Meta:
        db_table = "core_document_type"

    def __str__(self):
        return self.type


class Document(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_user"
    )

    type_document = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        db_column="id_type_document"
    )

    ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    creation_date = models.DateTimeField(
        auto_now_add=True
    )

    size = models.IntegerField(
        null=True,
        blank=True
    )

    document_name = models.CharField(
        max_length=255
    )

    internal_name = models.CharField(
        max_length=255
    )

    file_type = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    route = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    class Meta:
        db_table = "core_document"

    def __str__(self):
        return self.document_name