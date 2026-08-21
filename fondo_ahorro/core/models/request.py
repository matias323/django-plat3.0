from django.db import models
from .base import BaseModel


class RequestType(BaseModel):
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "core_request_type"

    def __str__(self):
        return self.name


class RequestStatus(BaseModel):
    status_type = models.CharField(max_length=100)

    class Meta:
        db_table = "core_request_status"

    def __str__(self):
        return self.status_type


class Request(BaseModel):
    request_type = models.ForeignKey(
        RequestType,
        on_delete=models.PROTECT,
        db_column="id_request_type",
    )

    status = models.ForeignKey(
        RequestStatus,
        on_delete=models.PROTECT,
        db_column="id_status",
    )

    class Meta:
        db_table = "core_request"

    def __str__(self):
        return f"Request {self.id} - {self.request_type}"