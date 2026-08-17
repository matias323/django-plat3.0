from django.db import models


class RequestType(models.Model):
    type = models.CharField(max_length=100)
    state = models.IntegerField(default=1)

    class Meta:
        db_table = "core_request_type"

    def __str__(self):
        return self.type


class RequestStatus(models.Model):
    status_type = models.CharField(max_length=100)
    state = models.IntegerField(default=1)

    class Meta:
        db_table = "core_request_status"

    def __str__(self):
        return self.status_type


class Request(models.Model):
    request_type = models.ForeignKey(
        RequestType,
        on_delete=models.PROTECT,
        db_column="id_request_type",
    )

    date = models.DateTimeField(
        null=True,
        blank=True,
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