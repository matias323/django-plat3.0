from django.db import migrations


def create_core_log(apps, schema_editor):
    LogModel = apps.get_model("core", "LogModel")

    existing_tables = schema_editor.connection.introspection.table_names()

    if LogModel._meta.db_table not in existing_tables:
        schema_editor.create_model(LogModel)


def remove_core_log(apps, schema_editor):
    LogModel = apps.get_model("core", "LogModel")

    existing_tables = schema_editor.connection.introspection.table_names()

    if LogModel._meta.db_table in existing_tables:
        schema_editor.delete_model(LogModel)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_remove_partnerreentry_unique_active_partner_reentry_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_core_log,
            remove_core_log,
        ),
    ]