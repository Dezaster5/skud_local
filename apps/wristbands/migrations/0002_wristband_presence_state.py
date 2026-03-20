from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wristbands", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wristband",
            name="presence_state",
            field=models.CharField(
                choices=[("unknown", "Unknown"), ("inside", "Inside"), ("outside", "Outside")],
                db_index=True,
                default="unknown",
                max_length=16,
            ),
        ),
    ]
