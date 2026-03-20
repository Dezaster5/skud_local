from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("access", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="accesspoint",
            name="reader_ip_address",
            field=models.GenericIPAddressField(
                blank=True,
                help_text="IP address of the physical Fondvision/ER80 reader tied to this access point.",
                null=True,
                unique=True,
            ),
        ),
    ]
