import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("controllers", "0002_controller_runtime_state_and_set_door_params"),
        ("events", "0001_initial"),
        ("wristbands", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FondvisionRequestLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sender_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("request_path", models.CharField(max_length=255)),
                ("query_string", models.TextField(blank=True)),
                ("request_body", models.TextField(blank=True)),
                ("raw_query_params", models.JSONField(blank=True, default=dict)),
                ("cardid", models.CharField(blank=True, db_index=True, max_length=64)),
                ("mjihao", models.CharField(blank=True, max_length=32)),
                ("cjihao", models.CharField(blank=True, db_index=True, max_length=64)),
                ("status", models.CharField(blank=True, max_length=32)),
                ("device_time_raw", models.CharField(blank=True, max_length=64)),
                ("device_time", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "access_event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fondvision_request_logs",
                        to="events.accessevent",
                    ),
                ),
                (
                    "controller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fondvision_request_logs",
                        to="controllers.controller",
                    ),
                ),
                (
                    "wristband",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fondvision_request_logs",
                        to="wristbands.wristband",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="fondvisionrequestlog",
            index=models.Index(fields=["controller", "created_at"], name="fondvision_ctrl_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="fondvisionrequestlog",
            index=models.Index(fields=["cjihao", "created_at"], name="fondvision_cjihao_ts_idx"),
        ),
    ]
