from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_rename_type_documenttype_name_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='DROP INDEX IF EXISTS "unique_active_partner_reentry";',
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="partnerreentry",
                    name="unique_active_partner_reentry",
                ),
            ],
        ),

        migrations.AddConstraint(
            model_name="partnerreentry",
            constraint=models.UniqueConstraint(
                fields=("partner",),
                condition=models.Q(is_active=True),
                name="unique_active_partner_reentry",
            ),
        ),
    ]