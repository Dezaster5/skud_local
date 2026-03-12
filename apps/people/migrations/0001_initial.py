from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Person",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("first_name", models.CharField(max_length=128)),
                ("last_name", models.CharField(max_length=128)),
                ("middle_name", models.CharField(blank=True, max_length=128)),
                (
                    "person_type",
                    models.CharField(
                        choices=[
                            ("employee", "Employee"),
                            ("visitor", "Visitor"),
                            ("contractor", "Contractor"),
                            ("administrator", "Administrator"),
                        ],
                        default="employee",
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("inactive", "Inactive"),
                            ("suspended", "Suspended"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=32,
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("note", models.TextField(blank=True)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["last_name", "first_name", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="person",
            index=models.Index(fields=["last_name", "first_name"], name="people_person_name_idx"),
        ),
    ]
