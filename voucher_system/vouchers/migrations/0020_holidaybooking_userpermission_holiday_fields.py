from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vouchers', '0019_alter_voucher_account_details_onlineattachment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HolidayBooking',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_number', models.CharField(blank=True, max_length=20)),
                ('trip_date', models.DateField()),
                ('destination', models.CharField(max_length=200)),
                ('departure_location', models.CharField(max_length=200)),
                ('departure_time', models.TimeField()),
                ('return_time', models.TimeField(blank=True, null=True)),
                ('bus_type', models.CharField(choices=[('MINI', 'Mini Bus (15-20 seats)'), ('STANDARD', 'Standard Bus (35-45 seats)'), ('LUXURY', 'Luxury Coach (45-55 seats)')], default='STANDARD', max_length=20)),
                ('no_of_passengers', models.IntegerField()),
                ('booked_by', models.CharField(max_length=200)),
                ('contact_number', models.CharField(max_length=15)),
                ('fare_per_person', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('advance_amount', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=12, null=True)),
                ('special_instructions', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='holidays', to='vouchers.company')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='holiday_bookings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('company', 'booking_number')},
            },
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_create_holiday',
            field=models.BooleanField(default=True, help_text='User can create holiday bookings'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_edit_holiday',
            field=models.BooleanField(default=False, help_text='User can edit holiday bookings'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_delete_holiday',
            field=models.BooleanField(default=False, help_text='User can delete holiday bookings'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_view_holiday_list',
            field=models.BooleanField(default=True, help_text='User can view holiday calendar'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_view_holiday_detail',
            field=models.BooleanField(default=True, help_text='User can view holiday booking details'),
        ),
    ]
