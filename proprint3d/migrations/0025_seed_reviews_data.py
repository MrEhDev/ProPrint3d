from django.db import migrations

def seed_reviews(apps, schema_editor):
    Review = apps.get_model('proprint3d', 'Review')
    REVIEWS = [
        {
            "client_name": "S.C.D. E.",
            "text": "Todo perfecto 💯 recomendable. Un verdadero placer.",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Julia G.",
            "text": "Todo correcto, perfecto estado, rápido el envío, recomendable 💯",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Francisco J.",
            "text": "Trato muy amable y me ha guiado para conseguir el producto que necesitaba.",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Edgar M.",
            "text": "Todo perfecto. Vendedor muy atento y recomendable.",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Jeremy G.",
            "text": "Todo perfecto, me aclaro todas las dudas que tenia, el producto llego en perfectas condiciones y el envio rapidisimo, muchas gracias, lo recomiendo",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Juan L.",
            "text": "Trato genial, hecho a medida como queria, todo perfecto i con un detalle sorpresa! Lo recomiendo 100%",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Àxel M.",
            "text": "Una pasada! Rápido, muy amable y un trabajo y entrega....impecable. Súper recomendable. Muchas gracias!",
            "rating": 5,
            "source": "Wallapop",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Marc S.",
            "text": "Pedí una pieza técnica a medida para el taller y la resistencia es impresionante. Ajuste al milímetro.",
            "rating": 5,
            "source": "Web",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
        {
            "client_name": "Daniel R.",
            "text": "Muy contento con la compra online. El acabado de las capas no se nota nada y llegó perfectamente embalado.",
            "rating": 5,
            "source": "Web",
            "client_details": "",
            "time_ago": "",
            "is_active": True,
        },
    ]

    for r in REVIEWS:
        Review.objects.update_or_create(
            client_name=r["client_name"],
            defaults=r
        )

def unseed_reviews(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('proprint3d', '0024_review_client_details_review_source_review_time_ago'),
    ]

    operations = [
        migrations.RunPython(seed_reviews, unseed_reviews),
    ]
