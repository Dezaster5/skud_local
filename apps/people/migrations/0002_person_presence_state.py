from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("people", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="presence_state",
            field=models.CharField(
                choices=[
                    ("unknown", "Unknown"),
                    ("inside", "Inside"),
                    ("outside", "Outside"),
                ],
                db_index=True,
                default="unknown",
                max_length=16,
            ),
        ),
    ]
