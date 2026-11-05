from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.db import models
import json
from django.core.serializers.json import DjangoJSONEncoder

from .models.log import LogModel
from .models.base import BaseModel

_estado_previo = {}

def sanitizar_datos(valor):
    """
    Recorre recursivamente los datos y convierte cualquier objeto de Django 
    (o lista de objetos) en su ID numérico o texto para que JSON pueda leerlo.
    """
    if hasattr(valor, 'pk'):  # Si es una instancia de un modelo de Django
        return valor.pk
    elif hasattr(valor, '__iter__') and not isinstance(valor, (str, bytes, dict)): # Si es una lista o QuerySet
        return [sanitizar_datos(v) for v in valor]
    elif isinstance(valor, dict): # Si es un diccionario
        return {k: sanitizar_datos(v) for k, v in valor.items()}
    elif hasattr(valor, 'name') and not isinstance(valor, str): # Si es un archivo (FileField)
        return str(valor.name)
    return valor

def convertir_json(data):
    if data is None:
        return None
    
    datos_limpios = sanitizar_datos(data)
    return json.loads(json.dumps(datos_limpios, cls=DjangoJSONEncoder))

@receiver(pre_save)
def estado_previo(sender, instance, **kwargs):
    if(issubclass(sender, BaseModel) and sender != LogModel and instance.pk):
        try:
            objeto_actual = sender.objects.get(pk=instance.pk)
            _estado_previo[(sender, instance.pk)] = model_to_dict(objeto_actual)
        except sender.DoesNotExist:
            pass

@receiver(post_save)
def registrar_guardado(sender, instance, created, **kwargs):
    if issubclass(sender, BaseModel) and sender != LogModel:
        datos_previos = _estado_previo.pop((sender, instance.pk), None)
        datos_nuevos = model_to_dict(instance)
        
        #convertir a json
        datos_previos = convertir_json(datos_previos)
        datos_nuevos = convertir_json(datos_nuevos)
        
        #usuario 
        usuario_accion = getattr(instance, 'user_update', None) or getattr(instance, 'user_create', None)
        
        LogModel.objects.create(
            table_name = sender._meta.db_table,
            record_id = instance.pk,
            action = 'CREATE' if created else 'UPDATE',
            user = usuario_accion,
            previous_data = datos_previos,
            new_data = datos_nuevos
        )
        
@receiver(post_delete)
def registrar_eliminacion(sender, instance, **kwargs):
    if issubclass(sender, BaseModel) and sender != LogModel:
        datos_previos = model_to_dict(instance)
        datos_previos = convertir_json(datos_previos)
        LogModel.objects.create(
            table_name = sender._meta.db_table,
            record_id = instance.pk,
            action = 'DELETE',
            user = getattr(instance, "user_update", None),
            previous_data = datos_previos,
            new_data = None
        )
        
