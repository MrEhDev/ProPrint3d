import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proprint3d_project.settings')
django.setup()

from proprint3d.models import Branch, Filament

def seed():
    branch = Branch.objects.filter(is_main=True).first() or Branch.objects.first()
    if not branch:
        print("No branch found")
        return

    if Filament.objects.filter(branch=branch).exists():
        print(f"Filaments already exist for {branch.name}")
        return

    initial = [
        (1, "Bambu Lab", "PLA Basic", "Negro", "#111111", 2, 1, 1, 20.0),
        (2, "Bambu Lab", "PLA Basic", "Blanco", "#f5f5f5", 3, 1, 1, 20.0),
        (3, "eSun", "PLA+", "Gris", "#78716c", 2, 1, 1, 18.5),
        (4, "Elegoo", "PLA", "Blanco", "#ffffff", 2, 3, 1, 15.0),
        (5, "Sunlu", "PLA+", "Rojo", "#dc2626", 1, 1, 1, 17.0),
        (6, "eSun", "PLA+", "Azul", "#2563eb", 1, 1, 1, 18.5),
        (7, "Bambu Lab", "PETG Basic", "Negro", "#1e293b", 1, 1, 1, 21.0),
        (8, "Sunlu", "TPU 95A", "Negro", "#0f172a", 0, 1, 1, 28.0),
        (9, "Bambu Lab", "PLA Matte", "Verde Bosque", "#15803d", 1, 1, 1, 22.0),
        (10, "Sunlu", "PLA+", "Naranja", "#ea580c", 1, 1, 1, 17.0),
    ]

    for code, brand, mat, color, hex_val, closed, opened, alert, cost in initial:
        Filament.objects.create(
            branch=branch, code=code, brand=brand, material=mat, color_name=color,
            color_hex=hex_val, spools_closed=closed, spools_opened=opened,
            min_closed_alert=alert, cost_per_kg=cost
        )
    print(f"Seeded {len(initial)} filaments for {branch.name}")

if __name__ == '__main__':
    seed()
