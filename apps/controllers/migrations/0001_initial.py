import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Controller",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("serial_number", models.CharField(max_length=64, unique=True)),
                (
                    "controller_type",
                    models.CharField(
                        choices=[
                            ("ironlogic_z5r_web_bt", "IronLogic Z-5R Web BT"),
                            ("generic_web_json", "Generic Web-JSON"),
                        ],
                        default="ironlogic_z5r_web_bt",
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("offline", "Offline"),
                            ("maintenance", "Maintenance"),
                            ("disabled", "Disabled"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=32,
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("firmware_version", models.CharField(blank=True, max_length=64)),
                ("description", models.TextField(blank=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["name", "serial_number"],
            },
        ),
        migrations.CreateModel(
            name="ControllerTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "task_type",
                    models.CharField(
                        choices=[
                            ("set_active", "Set active"),
                            ("open_door", "Open door"),
                            ("add_wristbands", "Add wristbands"),
                            ("del_wristbands", "Delete wristbands"),
                            ("clear_cards", "Clear cards"),
                            ("set_mode", "Set mode"),
                            ("set_timezone", "Set timezone"),
                            ("read_cards", "Read cards"),
                            ("sync_wristbands", "Sync wristbands"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("done", "Done"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "priority",
                    models.PositiveSmallIntegerField(
                        db_index=True,
                        default=100,
                        help_text="Lower value means higher execution priority.",
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("scheduled_for", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "controller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tasks",
                        to="controllers.controller",
                    ),
                ),
            ],
            options={
                "ordering": ["priority", "created_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="controllertask",
            index=models.Index(
                fields=["controller", "status", "scheduled_for"],
                name="ctrltask_pickup_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="controllertask",
            index=models.Index(
                fields=["controller", "status", "priority"],
                name="ctrltask_priority_idx",
            ),
        ),
    ]
