from django.db import migrations

def assign_to_spain(apps, schema_editor):
    Branch = apps.get_model('proprint3d', 'Branch')
    Order = apps.get_model('proprint3d', 'Order')
    Customer = apps.get_model('proprint3d', 'Customer')
    Quote = apps.get_model('proprint3d', 'Quote')

    spain = Branch.objects.filter(slug='espana').first() or Branch.objects.filter(is_main=True).first()
    if spain:
        Order.objects.filter(branch__isnull=True).update(branch=spain)
        Customer.objects.filter(branch__isnull=True).update(branch=spain)
        Quote.objects.filter(branch__isnull=True).update(branch=spain)

def reverse_assign(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('proprint3d', '0028_seed_branches_data'),
    ]

    operations = [
        migrations.RunPython(assign_to_spain, reverse_code=reverse_assign),
    ]

