from django.db import models
from core.models.base import BaseModel
from core.models.person import Person
from core.models.document import Document

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from applications.contabilidad.asientos_contables.models import AsientoContable

# Create your models here.

# Deposito
class Deposit(BaseModel):
    date = models.DateField(null=False, blank=False, verbose_name="Fecha Deposito")
    amount = models.PositiveBigIntegerField(null=False, blank=False, verbose_name="Monto")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Persona")
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name="Descripcion")
    deposit_number = models.PositiveBigIntegerField(null=False, blank=False, verbose_name="Numero Deposito")
    voucher_number = models.CharField(max_length=20, null=True, blank=True, verbose_name="Numero Comprobante")
    
    class Meta:
        db_table = "core_deposit"
        verbose_name = "Deposito"
        verbose_name_plural = "Depositos"
        
    def __str__(self):
        return f"{self.deposit_number} - {self.amount}"
    
    def deposit_to_dic(self):
        return {
            "deposit" : {
                "id" : self.id,
                "amount" : self.amount,
                "date" : self.date,
                "person" : self.person.get_full_name(),
                "deposit_number" : self.deposit_number,
                "voucher_number" : self.voucher_number,
                "description" : self.description,
            },
            "applications" : [
                app.deposit_application_to_dic()
                for app in self.applications.select_related("process_type", "application_content_type").all()
            ]
        }
    
# tipo de proceso
class ProcessType(BaseModel):
    description = models.CharField(max_length=200, null=False, blank=False, verbose_name="Descripcion")
    
    class Meta:
        db_table = "core_deposit_process_type"
        verbose_name = "Tipo de Proceso Deposito"
        verbose_name_plural = "Tipos de Procesos Depositos"
        
    def __str__(self):
        return f"{self.description}"
    

        
#deposito aplicacion
class DepositApplication(BaseModel):
    deposit = models.ForeignKey(Deposit, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Deposito", related_name="applications")
    amount = models.PositiveBigIntegerField(null=False, blank=False, verbose_name="Monto")
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name="Descripcion")
    application  = GenericForeignKey("application_content_type", "application_object_id")
    application_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Tipo de aplicacion")
    application_object_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="ID de Aplicacion")
    process_type = models.ForeignKey(ProcessType, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Tipo de Proceso")

    class Meta:
        db_table = "core_deposit_application"
        verbose_name = "Deposito Aplicacion"
        verbose_name_plural = "Deposito Aplicaciones"
        
    # obtener asiento contable
    def get_asiento_contable(self):
        # busco asiento contable en el "origen" donde la se encuentre la instancia de depositApplication
        try:
            ct = ContentType.objects.get_for_model(self)
            return AsientoContable.objects.filter(origen_content_type=ct, origen_object_id=self.id).first()
        except Exception:
            return None
        
    def deposit_application_to_dic(self):
        obj_afectado = self.application
        asiento_contable = self.get_asiento_contable()
        
        #objeto afectado
        obj_data = None
        if obj_afectado:
            if hasattr(obj_afectado, "to_dict"):
                obj_data = obj_afectado.to_dict()
            else:
                obj_data = {
                    "tipo" : self.application_content_type.model,
                    "id" : self.application_object_id,
                    "representacion" : str(obj_afectado)
                }
        
        asiento_data = None
        if asiento_contable:
            if hasattr(asiento_contable, "to_dict"):
                asiento_data = asiento_contable.to_dict()
            else:
                asiento_data = {
                    "id" : asiento_contable.id,
                    "numero_asiento" : asiento_contable.entry_number,
                    "fecha_asiento" : asiento_contable.entry_date, 
                }

        return {
            "id" : self.id,
            "amount" : self.amount,
            "description" : self.description,
            "proceso" : {
                "id" : self.process_type.id,
                "descripcion" : self.process_type.description,
            },
            "objeto_afectado" : obj_data,
            "asiento_contable" : asiento_data,
            "document" : self.deposit.document_to_dic()
        }
        
class DepositDocument(BaseModel):
    document = models.ForeignKey(Document, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Documento", related_name="documents")
    deposit = models.ForeignKey(Deposit, on_delete=models.PROTECT, null=False, blank=False, verbose_name="Deposito", related_name="documents")
    
    class Meta():
        db_table = "core_deposit_document"
        verbose_name = "Deposito Documento"
        verbose_name_plural = "Depositos Documentos"
        
    def document_to_dic(self):
        return {
            "id" : self.id,
            "url" : self.document.route,
            "file_type" : self.document.file_type,
            "internal_name" : self.document.internal_name,
            "size" : self.document.size
        }