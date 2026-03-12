import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("access", "0001_initial"),
        ("controllers", "0001_initial"),
        ("people", "0001_initial"),
        ("wristbands", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("credential_uid", models.CharField(blank=True, max_length=64)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("access_check", "Access check"),
                            ("access_granted", "Access granted"),
                            ("access_denied", "Access denied"),
                            ("controller_event", "Controller event"),
                            ("sync_event", "Sync event"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[("entry", "Entry"), ("exit", "Exit"), ("unknown", "Unknown")],
                        default="unknown",
                        max_length=16,
                    ),
                ),
                (
                    "decision",
                    models.CharField(
                        choices=[("granted", "Granted"), ("denied", "Denied"), ("unknown", "Unknown")],
                        db_index=True,
                        default="unknown",
                        max_length=16,
                    ),
                ),
                ("reason_code", models.CharField(blank=True, max_length=64)),
                ("message", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                (
                    "access_point",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_events",
                        to="access.accesspoint",
                    ),
                ),
                (
                    "controller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_events",
                        to="controllers.controller",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_events",
                        to="people.person",
                    ),
                ),
                (
                    "wristband",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_events",
                        to="wristbands.wristband",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("admin", "Admin"),
                            ("api", "API"),
                            ("system", "System"),
                            ("controller", "Controller"),
                        ],
                        db_index=True,
                        default="system",
                        max_length=16,
                    ),
                ),
                ("action", models.CharField(db_index=True, max_length=64)),
                ("object_type", models.CharField(max_length=64)),
                ("object_id", models.CharField(max_length=64)),
                ("object_repr", models.CharField(max_length=255)),
                ("details", models.JSONField(blank=True, default=dict)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="accessevent",
            index=models.Index(fields=["controller", "created_at"], name="accessevent_ctrl_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="accessevent",
            index=models.Index(fields=["access_point", "created_at"], name="accessevent_point_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["object_type", "object_id"], name="auditlog_object_idx"),
        ),
    ]
