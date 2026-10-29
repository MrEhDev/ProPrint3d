from django.db import migrations

def copy_categories(apps, schema_editor):
    Product = apps.get_model('proprint3d', 'Product')
    for product in Product.objects.all():
        if product.category_id:
            product.categories.add(product.category_id)

def reverse_copy_categories(apps, schema_editor):
    Product = apps.get_model('proprint3d', 'Product')
    for product in Product.objects.all():
        first_cat = product.categories.first()
        if first_cat:
            product.category = first_cat
            product.save(update_fields=['category'])

class Migration(migrations.Migration):

    dependencies = [
        ('proprint3d', '0018_product_categories_alter_product_category'),
    ]

    operations = [
        migrations.RunPython(copy_categories, reverse_copy_categories),
    ]
