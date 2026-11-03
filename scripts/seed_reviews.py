import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proprint3d_project.settings')
django.setup()

from proprint3d.models import Review

REVIEWS = [
    {
        "client_name": "S.C.D. E.",
        "text": "Todo perfecto 💯 recomendable. Un verdadero placer.",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "11 años en Wallapop",
        "time_ago": "Hace 1 mes",
    },
    {
        "client_name": "Julia G.",
        "text": "Todo correcto, perfecto estado, rápido el envío, recomendable 💯",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "10 años en Wallapop",
        "time_ago": "Hace 2 meses",
    },
    {
        "client_name": "Francisco J.",
        "text": "Trato muy amable y me ha guiado para conseguir el producto que necesitaba.",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "1 año en Wallapop",
        "time_ago": "Hace 4 meses",
    },
    {
        "client_name": "Edgar M.",
        "text": "Todo perfecto. Vendedor muy atento y recomendable.",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "9 años en Wallapop",
        "time_ago": "Hace 4 meses",
    },
    {
        "client_name": "Jeremy G.",
        "text": "Todo perfecto, me aclaro todas las dudas que tenia, el producto llego en perfectas condiciones y el envio rapidisimo, muchas gracias, lo recomiendo",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "8 años en Wallapop",
        "time_ago": "Hace 4 meses",
    },
    {
        "client_name": "Juan L.",
        "text": "Trato genial, hecho a medida como queria, todo perfecto i con un detalle sorpresa! Lo recomiendo 100%",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "11 años en Wallapop",
        "time_ago": "Hace 5 meses",
    },
    {
        "client_name": "Àxel M.",
        "text": "Una pasada! Rápido, muy amable y un trabajo y entrega....impecable. Súper recomendable. Muchas gracias!",
        "rating": 5,
        "source": "Wallapop",
        "client_details": "12 años en Wallapop",
        "time_ago": "Hace 6 meses",
    },
]

for r in REVIEWS:
    obj, created = Review.objects.update_or_create(
        client_name=r["client_name"],
        defaults=r
    )
    status = "Creada" if created else "Actualizada"
    print(f"[{status}] {obj.client_name} - {obj.rating}★")

print(f"Total reviews activas: {Review.objects.filter(is_active=True).count()}")
