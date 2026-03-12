import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("controllers", "0001_initial"),
        ("people", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TimeZoneRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128, unique=True)),
                ("description", models.TextField(blank=True)),
                ("timezone_name", models.CharField(default="Asia/Almaty", max_length=64)),
                (
                    "weekdays",
                    models.JSONField(
                        default=list,
                        help_text="ISO weekday numbers 1-7. Overnight windows are allowed via start_time > end_time.",
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="AccessPoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=128)),
                (
                    "direction",
                    models.CharField(
                        choices=[
                            ("entry", "Entry"),
                            ("exit", "Exit"),
                            ("bidirectional", "Bidirectional"),
                        ],
                        default="entry",
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("inactive", "Inactive"),
                            ("maintenance", "Maintenance"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=32,
                    ),
                ),
                ("device_port", models.PositiveSmallIntegerField(default=1)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "controller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="access_points",
                        to="controllers.controller",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="AccessPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "effect",
                    models.CharField(
                        choices=[("allow", "Allow"), ("deny", "Deny")],
                        default="allow",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("inactive", "Inactive")],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                (
                    "priority",
                    models.PositiveSmallIntegerField(
                        db_index=True,
                        default=100,
                        help_text="Lower value means higher policy priority.",
                    ),
                ),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                (
                    "access_point",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_policies",
                        to="access.accesspoint",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_policies",
                        to="people.person",
                    ),
                ),
                (
                    "timezone_rule",
                    models.ForeignKey(
                        blank=True,
                        help_text="Leave empty for 24/7 access. This is the current simple model for unrestricted access.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="access_policies",
                        to="access.timezonerule",
                    ),
                ),
            ],
            options={
                "ordering": ["priority", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="accesspoint",
            index=models.Index(fields=["controller", "status"], name="accesspoint_ctrl_stat_idx"),
        ),
        migrations.AddIndex(
            model_name="accesspolicy",
            index=models.Index(
                fields=["person", "access_point", "status"],
                name="policy_person_point_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="accesspolicy",
            index=models.Index(
                fields=["access_point", "status", "priority"],
                name="policy_point_status_idx",
            ),
        ),
    ]
