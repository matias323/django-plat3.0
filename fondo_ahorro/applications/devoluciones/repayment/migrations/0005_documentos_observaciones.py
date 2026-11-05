from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import applications.devoluciones.repayment.models.documento


def sembrar_tipos(apps, schema_editor):
    Tipo = apps.get_model('repayment', 'DevoDocumentoTipo')
    datos = [
        ('solicitud-personal', 'Solicitud personal'),
        ('solicitud-personal-f', 'Solicitud personal (F)'),
        ('resolucion-exenta', 'Resolución exenta'),
        ('documento-identificacion', 'Documento de identificación'),
        ('vivienda-fiscal', 'Vivienda fiscal'),
        ('solicitud-pago-anticipado', 'Solicitud pago anticipado'),
    ]
    for orden, (codigo, nombre) in enumerate(datos, 1):
        Tipo.objects.using(schema_editor.connection.alias).get_or_create(
            codigo=codigo, defaults={'nombre': nombre, 'orden': orden,
                                     'user_create_id': None, 'user_update_id': None})


def auditoria_base():
    return [
        ('id', models.BigAutoField(primary_key=True, serialize=False)),
        ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha Creación')),
        ('updated_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha Modificación')),
        ('is_active', models.BooleanField(default=True, verbose_name='Es Activo')),
        ('user_create', models.ForeignKey(default=1, null=True, on_delete=django.db.models.deletion.PROTECT,
            related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Usuario Creador')),
        ('user_update', models.ForeignKey(default=1, null=True, on_delete=django.db.models.deletion.PROTECT,
            related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Usuario Modificador')),
    ]


class Migration(migrations.Migration):
    dependencies = [
        ('repayment', '0004_devoconsejoestado_alter_devoconsejo_estado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DevoDocumentoTipo',
            fields=auditoria_base() + [
                ('codigo', models.SlugField(max_length=60, unique=True)),
                ('nombre', models.CharField(max_length=150)),
                ('orden', models.PositiveSmallIntegerField(default=0)),
            ],
            options={'db_table': 'devo_documento_tipo', 'ordering': ['orden', 'pk']},
        ),
        migrations.CreateModel(
            name='DevoDocumento',
            fields=auditoria_base() + [
                ('archivo', models.FileField(max_length=350, upload_to=applications.devoluciones.repayment.models.documento.ruta_documento)),
                ('nombre_original', models.CharField(max_length=255)),
                ('estado', models.CharField(choices=[('pendiente','Pendiente'),('aprobado','Aprobado'),('rechazado','Rechazado')], max_length=12, default='pendiente')),
                ('version', models.PositiveIntegerField(default=1)),
                ('vigente', models.BooleanField(default=True)),
                ('solicitud', models.ForeignKey(db_column='id_devo_solicitud', on_delete=django.db.models.deletion.PROTECT, related_name='documentos', to='repayment.devosolicitud')),
                ('tipo', models.ForeignKey(db_column='id_tipo_documento', on_delete=django.db.models.deletion.PROTECT, related_name='documentos', to='repayment.devodocumentotipo')),
            ],
            options={'db_table': 'devo_documento', 'ordering': ['-created_at','-pk']},
        ),
        migrations.CreateModel(
            name='DevoObservacion',
            fields=auditoria_base() + [
                ('accion', models.CharField(max_length=35, choices=[('solicitud_creada','Solicitud creada'),('estado_solicitud','Estado de solicitud'),('consejo','Consejo actualizado'),('documento_adjuntado','Documento adjuntado'),('documento_reemplazado','Documento reemplazado'),('documento_eliminado','Documento eliminado'),('estado_documento','Estado de documento'),('comentario','Comentario')])),
                ('descripcion', models.TextField()),
                ('solicitud', models.ForeignKey(db_column='id_devo_solicitud', on_delete=django.db.models.deletion.PROTECT, related_name='observaciones', to='repayment.devosolicitud')),
                ('documento', models.ForeignKey(blank=True, null=True, db_column='id_documento', on_delete=django.db.models.deletion.PROTECT, related_name='observaciones', to='repayment.devodocumento')),
            ],
            options={'db_table': 'devo_observacion', 'ordering': ['-created_at','-pk']},
        ),
        migrations.AddConstraint(
            model_name='devodocumento',
            constraint=models.UniqueConstraint(fields=('solicitud','tipo'), condition=models.Q(vigente=True), name='devo_doc_unico_vigente'),
        ),
        migrations.RunPython(sembrar_tipos, migrations.RunPython.noop),
    ]
