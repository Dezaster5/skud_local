from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("controllers", "0002_controller_runtime_state_and_set_door_params"),
    ]

    operations = [
        migrations.AlterField(
            model_name="controller",
            name="controller_type",
            field=models.CharField(
                choices=[
                    ("ironlogic_z5r_web_bt", "IronLogic Z-5R Web BT"),
                    ("fondvision_er80", "Fondvision ER80"),
                    ("generic_web_json", "Generic Web-JSON"),
                ],
                default="ironlogic_z5r_web_bt",
                max_length=64,
            ),
        ),
        migrations.CreateModel(
            name="Reader",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("ip_address", models.GenericIPAddressField(unique=True)),
                (
                    "external_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Reader identifier reported by Fondvision devices, for example cjihao.",
                        max_length=64,
                    ),
                ),
                (
                    "device_number",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        db_index=True,
                        help_text="Optional numeric reader/channel identifier, for example mjihao.",
                        null=True,
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[("entry", "Entry"), ("exit", "Exit")],
                        db_index=True,
                        default="entry",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("inactive", "Inactive"), ("maintenance", "Maintenance")],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "controller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="readers",
                        to="controllers.controller",
                    ),
                ),
            ],
            options={
                "ordering": ["controller__name", "name", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="reader",
            index=models.Index(fields=["controller", "status"], name="reader_ctrl_status_idx"),
        ),
        migrations.AddIndex(
            model_name="reader",
            index=models.Index(fields=["external_id"], name="reader_external_id_idx"),
        ),
        migrations.AddIndex(
            model_name="reader",
            index=models.Index(fields=["controller", "device_number"], name="reader_ctrl_number_idx"),
        ),
    ]
