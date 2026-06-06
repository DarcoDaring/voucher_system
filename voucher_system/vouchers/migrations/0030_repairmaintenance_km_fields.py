from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vouchers', '0029_holiday_completed_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='repairmaintenance',
            name='starting_km',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='repairmaintenance',
            name='starting_km_attachment',
            field=models.FileField(blank=True, null=True, upload_to='repair/km_attachments/'),
        ),
        migrations.AddField(
            model_name='repairmaintenance',
            name='ending_km',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='repairmaintenance',
            name='ending_km_attachment',
            field=models.FileField(blank=True, null=True, upload_to='repair/km_attachments/'),
        ),
    ]
