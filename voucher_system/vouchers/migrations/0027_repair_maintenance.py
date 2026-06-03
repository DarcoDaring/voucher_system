from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vouchers', '0026_holiday_bank_approver'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RepairMaintenance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('repair_number', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(
                    choices=[('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted to Bank'), ('APPROVED', 'Approved')],
                    default='DRAFT',
                    max_length=20,
                )),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='repairs',
                    to='vouchers.company',
                )),
                ('vehicle', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='repairs',
                    to='vouchers.vehicle',
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='repairs_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name='RepairItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='repair/attachments/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('repair', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='vouchers.repairmaintenance',
                )),
            ],
        ),
        migrations.CreateModel(
            name='RepairBankSettlement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bank_document', models.FileField(blank=True, null=True, upload_to='repair/bank/')),
                ('status', models.CharField(
                    choices=[('PENDING_APPROVAL', 'Pending Approval'), ('APPROVED', 'Approved')],
                    default='PENDING_APPROVAL',
                    max_length=20,
                )),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('repair', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bank',
                    to='vouchers.repairmaintenance',
                )),
                ('approved_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='repair_bank_approvals',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('submitted_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='repair_bank_submissions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
