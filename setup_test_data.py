import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proprint3d_project.settings')
django.setup()

from django.contrib.auth.models import User
from proprint3d.models import Category, Product

# Create Superuser (User: admin / Pass: admin)
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print("Superusuario creado con éxito (admin / admin).")
else:
    print("El superusuario ya existe.")

# Create Categories
cat_deco, _ = Category.objects.get_or_create(
    name='Decoración', 
    defaults={'description': 'Figuras decorativas para el hogar.'}
)
cat_func, _ = Category.objects.get_or_create(
    name='Mecánica y Funcional', 
    defaults={'description': 'Piezas de uso práctico y resistentes.'}
)

# Create Products
if not Product.objects.filter(title='Maceta Minimalista Low-Poly').exists():
    Product.objects.create(
        title='Maceta Minimalista Low-Poly',
        category=cat_deco,
        description='Maceta geométrica con diseño low poly moderno. Ideal para plantas pequeñas o suculentas. Impresa en PLA biodegradable.',
        price=18.50,
        weight_grams=110.0,
        print_time_hours=4.5,
        is_active=True
    )
    print("Producto de prueba 1 creado.")

if not Product.objects.filter(title='Soporte para Auriculares de Mesa').exists():
    Product.objects.create(
        title='Soporte para Auriculares de Mesa',
        category=cat_func,
        description='Soporte de escritorio muy estable y resistente. Mantiene tus auriculares seguros y tu mesa organizada. Impreso en PETG de alta resistencia.',
        price=24.90,
        weight_grams=165.0,
        print_time_hours=7.2,
        is_active=True
    )
    print("Producto de prueba 2 creado.")
