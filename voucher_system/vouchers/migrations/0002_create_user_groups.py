from django.db import migrations

def create_groups(apps, schema_editor):
    """Create Accountants and Admin Staff groups"""
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Accountants')
    Group.objects.get_or_create(name='Admin Staff')

def remove_groups(apps, schema_editor):
    """Remove groups if migration is reversed"""
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Accountants', 'Admin Staff']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('vouchers', '0001_initial'),  #  CHANGE THIS to your previous migration
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]