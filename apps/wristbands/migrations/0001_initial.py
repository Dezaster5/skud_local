import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("people", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Wristband",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uid", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("blocked", "Blocked"),
                            ("lost", "Lost"),
                            ("retired", "Retired"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=32,
                    ),
                ),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                (
                    "person",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wristbands",
                        to="people.person",
                    ),
                ),
            ],
            options={
                "ordering": ["uid"],
            },
        ),
        migrations.AddIndex(
            model_name="wristband",
            index=models.Index(fields=["status", "expires_at"], name="wristband_status_exp_idx"),
        ),
    ]
