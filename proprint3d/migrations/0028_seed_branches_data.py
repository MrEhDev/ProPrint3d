from django.db import migrations

def seed_branches(apps, schema_editor):
    Branch = apps.get_model('proprint3d', 'Branch')
    
    # 1. España (Principal)
    Branch.objects.get_or_create(
        slug='espana',
        defaults={
            'name': 'España',
            'whatsapp': '34660904515',
            'phone': '+34 660 90 45 15',
            'email': 'proprint3d.es@gmail.com',
            'greeting_name': 'ProPrint3D',
            'city': "Lliçà d'Amunt (Barcelona, España)",
            'address': '',
            'is_main': True,
            'is_active': True,
        }
    )
    
    # 2. Canarias
    Branch.objects.get_or_create(
        slug='canarias',
        defaults={
            'name': 'Canarias',
            'whatsapp': '34697868621',
            'phone': '+34 697 86 86 21',
            'email': 'proprint3d.es@gmail.com',
            'greeting_name': 'ProPrint3D Canarias',
            'city': 'Santa Cruz de Tenerife',
            'address': '',
            'is_main': False,
            'is_active': True,
        }
    )

def remove_branches(apps, schema_editor):
    Branch = apps.get_model('proprint3d', 'Branch')
    Branch.objects.filter(slug__in=['espana', 'canarias']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('proprint3d', '0027_branch_address_branch_city'),
    ]

    operations = [
        migrations.RunPython(seed_branches, reverse_code=remove_branches),
    ]

