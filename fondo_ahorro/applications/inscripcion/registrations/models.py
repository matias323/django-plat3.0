from django.db import models

from core.models.base import BaseModel
from core.models import Person, Document, Observation, Request


class RegistrationType(BaseModel):
    type = models.CharField(max_length=100)

    class Meta:
        db_table = "registration_type"
        verbose_name = "Tipo de inscripción"
        verbose_name_plural = "Tipos de inscripción"

    def __str__(self):
        return self.type


class Registration(BaseModel):
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

    user_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_column="user_ip",
    )

    class Meta:
        db_table = "registration"
        verbose_name = "Solicitud de inscripción"
        verbose_name_plural = "Solicitudes de inscripción"


class RegistrationDocumentStatus(BaseModel):
    status_type = models.CharField(max_length=100)

    class Meta:
        db_table = "registration_document_status"
        verbose_name = "Estado de documento"
        verbose_name_plural = "Estados de documentos"

    def __str__(self):
        return self.status_type


class RegistrationDocument(BaseModel):
    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        db_column="id_registration",
        related_name="documents",
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        db_column="id_document",
    )

    status = models.ForeignKey(
        RegistrationDocumentStatus,
        on_delete=models.PROTECT,
        db_column="id_status",
    )

    class Meta:
        db_table = "registration_document"
        verbose_name = "Documento de inscripción"
        verbose_name_plural = "Documentos de inscripción"

    def __str__(self):
        return f"{self.registration} - {self.document}"


class RegistrationObservation(BaseModel):
    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        db_column="id_registration",
        related_name="observations",
    )

    observation = models.ForeignKey(
        Observation,
        on_delete=models.PROTECT,
        db_column="id_observation",
    )

    class Meta:
        db_table = "registration_observation"
        verbose_name = "Observación de inscripción"
        verbose_name_plural = "Observaciones de inscripción"

    def __str__(self):
        return f"{self.registration} - {self.observation}"