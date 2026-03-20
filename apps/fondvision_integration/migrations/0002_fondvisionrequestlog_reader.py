import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("controllers", "0003_reader_and_controller_type"),
        ("fondvision_integration", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fondvisionrequestlog",
            name="reader",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fondvision_request_logs",
                to="controllers.reader",
            ),
        ),
        migrations.AddIndex(
            model_name="fondvisionrequestlog",
            index=models.Index(fields=["reader", "created_at"], name="fondvision_reader_ts_idx"),
        ),
    ]
