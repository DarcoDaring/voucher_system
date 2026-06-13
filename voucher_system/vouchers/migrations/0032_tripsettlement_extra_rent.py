from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vouchers', '0031_whatsapp_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='tripsettlement',
            name='extra_rent',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
