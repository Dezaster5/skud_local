import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("controllers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebJsonRequestLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=128)),
                ("operation", models.CharField(blank=True, db_index=True, max_length=64)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                (
                    "processing_status",
                    models.CharField(
                        choices=[
                            ("processed", "Processed"),
                            ("access_denied", "Access denied"),
                            ("rejected", "Rejected"),
                            ("invalid_payload", "Invalid payload"),
                            ("unknown_operation", "Unknown operation"),
                            ("controller_not_found", "Controller not found"),
                            ("controller_inactive", "Controller inactive"),
                            ("error", "Error"),
                        ],
                        db_index=True,
                        default="processed",
                        max_length=32,
                    ),
                ),
                ("http_status", models.PositiveSmallIntegerField(default=200)),
                ("token_present", models.BooleanField(default=False)),
                ("request_body", models.TextField(blank=True)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                (
                    "controller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="webjson_request_logs",
                        to="controllers.controller",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="webjsonrequestlog",
            index=models.Index(fields=["operation", "processing_status"], name="webjson_op_status_idx"),
        ),
        migrations.AddIndex(
            model_name="webjsonrequestlog",
            index=models.Index(fields=["controller", "created_at"], name="webjson_ctrl_created_idx"),
        ),
    ]

