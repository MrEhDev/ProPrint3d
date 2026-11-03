DEFAULT_REVIEWS = [
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

def ensure_default_reviews():
    """Siembra las valoraciones por defecto de forma idempotente."""
    from proprint3d.models import Review
    created_count = 0
    for r in DEFAULT_REVIEWS:
        _, created = Review.objects.update_or_create(
            client_name=r["client_name"],
            defaults=r
        )
        if created:
            created_count += 1
    return created_count

def get_verified_reviews(limit=None):
    """Obtiene las opiniones activas. Si no hay ninguna en la base de datos, siembra automáticamente las valoraciones oficiales."""
    from proprint3d.models import Review
    try:
        qs = Review.objects.filter(is_active=True).order_by('-created_at')
        if not qs.exists():
            ensure_default_reviews()
            qs = Review.objects.filter(is_active=True).order_by('-created_at')
        return qs[:limit] if limit else qs
    except Exception:
        return []
