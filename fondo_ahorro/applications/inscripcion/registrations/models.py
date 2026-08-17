from django.db import models
from django.conf import settings

from core.models import (
    Person,
    Document,
    Observation,
    Request,
)


class RegistrationType(models.Model):
    type = models.CharField(
        max_length=100
    )

    state = models.IntegerField(
        default=1
    )

    class Meta:
        db_table = "registration_type"

    def __str__(self):
        return self.type


class Registration(models.Model):
    request = models.OneToOneField(
        Request,
        on_delete=models.PROTECT,
        db_column="id_request",
        related_name="registration",
        null=False,
        blank=False,
    )

    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        db_column="id_person",
        null=True,
        blank=True,
    )

    registration_type = models.ForeignKey(
        RegistrationType,
        on_delete=models.PROTECT,
        db_column="id_registration_type",
    )

    contributes_a2 = models.IntegerField(
        null=True,
        blank=True,
        db_column="contributes_a2",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_user",
        null=True,
        blank=True,
    )

    user_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_column="user_ip",
    )

    class Meta:
        db_table = "registration"


class RegistrationDocumentStatus(models.Model):
    status_type = models.CharField(
        max_length=100
    )

    state = models.IntegerField(
        default=1
    )

    class Meta:
        db_table = "registration_document_status"

    def __str__(self):
        return self.status_type


class RegistrationDocument(models.Model):
    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        db_column="id_registration",
        related_name="documents"
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        db_column="id_document"
    )

    status = models.ForeignKey(
        RegistrationDocumentStatus,
        on_delete=models.PROTECT,
        db_column="id_status"
    )

    class Meta:
        db_table = "registration_document"

    def __str__(self):
        return f"{self.registration} - {self.document}"


class RegistrationObservation(models.Model):
    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        db_column="id_registration",
        related_name="observations"
    )

    observation = models.ForeignKey(
        Observation,
        on_delete=models.PROTECT,
        db_column="id_observation"
    )

    state = models.IntegerField(
        default=1
    )

    class Meta:
        db_table = "registration_observation"

    def __str__(self):
        return f"{self.registration} - {self.observation}"