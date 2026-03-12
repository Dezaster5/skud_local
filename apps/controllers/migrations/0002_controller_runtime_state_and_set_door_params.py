from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("controllers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="controller",
            name="active_state",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="controller",
            name="connection_firmware_version",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="controller",
            name="last_auth_hash",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="controller",
            name="mode_state",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="controllertask",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("set_active", "Set active"),
                    ("open_door", "Open door"),
                    ("set_door_params", "Set door params"),
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
    ]
