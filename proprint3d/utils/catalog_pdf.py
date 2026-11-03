import os
import io
import base64
import urllib.parse
import unicodedata
import re
from datetime import datetime
import qrcode
from PIL import Image
from django.conf import settings
from django.template.loader import render_to_string
import weasyprint

def generate_qr_base64(data_url):
    """Genera una imagen QR en formato data:image/png;base64."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=1,
    )
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

def file_to_base64(file_path):
    """Convierte un archivo en disco a data URI base64."""
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        ext = os.path.splitext(file_path)[1].lower().replace(".", "")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ("png" if ext == "png" else "octet-stream")
        return f"data:image/{mime};base64," + base64.b64encode(data).decode("utf-8")
    except Exception:
        return None

def get_product_image_base64(product, fallback_path):
    """Obtiene la imagen del producto en base64 o usa la imagen por defecto."""
    if product.main_image:
        try:
            path = product.main_image.path
            b64 = file_to_base64(path)
            if b64:
                return b64
        except Exception:
            pass
    return file_to_base64(fallback_path)

def sanitize_filename(name):
    normalized = unicodedata.normalize('NFKD', str(name or '')).encode('ASCII', 'ignore').decode('utf-8')
    clean = re.sub(r'[^\w\-]', '_', normalized).strip('_')
    return re.sub(r'_+', '_', clean) or "Catalogo"

def build_catalog_context(
    category_slug=None,
    category_slugs=None,
    include_prices=True,
    include_descriptions=False,
    custom_title=None,
    custom_subtitle=None,
    custom_slogan=None,
    custom_description=None,
):
    """Construye el contexto de datos para la plantilla del catálogo PDF agrupando por categoría."""
    from proprint3d.models import Category, Product

    static_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
    logo_path = os.path.join(static_dir, 'logo_square.png')
    hero_path = os.path.join(static_dir, 'hero_3d_render.png')

    logo_b64 = file_to_base64(logo_path) or file_to_base64(hero_path)
    fallback_img_b64 = file_to_base64(hero_path) or logo_b64

    # Normalizar lista de categorías seleccionadas
    slug_list = []
    if category_slugs:
        if isinstance(category_slugs, str):
            slug_list = [s.strip() for s in category_slugs.split(',') if s.strip()]
        else:
            slug_list = [str(s).strip() for s in category_slugs if str(s).strip()]
    elif category_slug:
        slug_list = [s.strip() for s in str(category_slug).split(',') if s.strip()]

    # Filtrar 'todas', 'todos', 'all'
    slug_list = [s for s in slug_list if s.lower() not in ('todas', 'todos', 'all', '')]

    selected_categories = []
    if slug_list:
        selected_categories = list(Category.objects.filter(slug__in=slug_list).order_by('name'))
    else:
        # Si no se seleccionó ninguna, se agrupan todas las categorías que tengan productos activos
        selected_categories = list(Category.objects.filter(products__is_active=True).distinct().order_by('name'))

    if slug_list and len(selected_categories) == 1:
        single_cat = selected_categories[0]
        category_name = single_cat.name
        category_description = single_cat.description or ""
    elif slug_list:
        category_name = " & ".join(c.name for c in selected_categories)
        category_description = f"Colección especial combinada: {category_name}."
    else:
        category_name = "Catálogo General"
        category_description = "Selección de piezas técnicas, decorativas y funcionales fabricadas en nuestro taller."

    is_holiday = any('navidad' in c.slug.lower() or 'navidad' in c.name.lower() for c in selected_categories)

    # Sobrescrituras de portada si el admin las especificó
    display_title = custom_title.strip() if (custom_title and custom_title.strip()) else category_name
    display_subtitle = custom_subtitle.strip() if (custom_subtitle and custom_subtitle.strip()) else "Colección Exclusiva"
    display_slogan = custom_slogan.strip() if (custom_slogan and custom_slogan.strip()) else "Fabricado con calidad y precisión"
    display_description = custom_description.strip() if (custom_description and custom_description.strip()) else (
        category_description or "Piezas terminadas con tecnología FDM de alta definición, filamentos técnicos y revisión artesanal en cada pedido."
    )

    wa_phone = "34660904515"
    # Si incluye descripciones -> tarjeta a lo ancho (3 por página) para evitar desbordamientos
    # Si no incluye descripciones -> rejilla compacta 2x2 (4 por página)
    chunk_size = 3 if include_descriptions else 4

    pages = []
    seen_product_ids = set()
    total_products_count = 0

    # Iterar por cada categoría para que cada página tenga exactamente el nombre de su categoría
    for cat in selected_categories:
        cat_products_qs = cat.products.filter(is_active=True).order_by('title')
        cat_items = []

        for p in cat_products_qs:
            if p.id in seen_product_ids:
                continue
            seen_product_ids.add(p.id)

            msg = f"Hola, me interesa la pieza '{p.title}' del catálogo de {cat.name}."
            wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(msg)}"
            qr_b64 = generate_qr_base64(wa_url)
            img_b64 = get_product_image_base64(p, hero_path)

            price_formatted = f"{float(p.price):.2f}".replace('.', ',') + " €"
            sale_price_formatted = f"{float(p.sale_price):.2f}".replace('.', ',') + " €" if p.sale_price else None

            desc_text = (p.description or '').strip()
            # En tarjeta horizontal hay ancho generoso (hasta 220 caracteres sin desbordar)
            short_desc = desc_text[:220] + ('...' if len(desc_text) > 220 else '')

            cat_items.append({
                'id': p.id,
                'title': p.title,
                'dimensions': p.dimensions,
                'description': desc_text,
                'short_description': short_desc,
                'price': price_formatted,
                'is_on_sale': p.is_on_sale and bool(p.sale_price),
                'sale_price': sale_price_formatted,
                'image_b64': img_b64,
                'qr_b64': qr_b64,
                'wa_url': wa_url,
                'category_name': cat.name,
            })

        if not cat_items:
            continue

        total_products_count += len(cat_items)

        # Dividir los productos de esta categoría en páginas con su encabezado correspondiente
        for i in range(0, len(cat_items), chunk_size):
            pages.append({
                'category_name': cat.name,
                'products': cat_items[i:i + chunk_size]
            })

    # Si hay productos sin categoría y estamos en catálogo general
    if not slug_list:
        orphan_qs = Product.objects.filter(is_active=True, categories__isnull=True).order_by('title')
        orphan_items = []
        for p in orphan_qs:
            if p.id in seen_product_ids:
                continue
            seen_product_ids.add(p.id)
            msg = f"Hola, me interesa la pieza '{p.title}' del catálogo."
            wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(msg)}"
            qr_b64 = generate_qr_base64(wa_url)
            img_b64 = get_product_image_base64(p, hero_path)
            price_formatted = f"{float(p.price):.2f}".replace('.', ',') + " €"
            sale_price_formatted = f"{float(p.sale_price):.2f}".replace('.', ',') + " €" if p.sale_price else None
            desc_text = (p.description or '').strip()
            short_desc = desc_text[:220] + ('...' if len(desc_text) > 220 else '')
            orphan_items.append({
                'id': p.id,
                'title': p.title,
                'dimensions': p.dimensions,
                'description': desc_text,
                'short_description': short_desc,
                'price': price_formatted,
                'is_on_sale': p.is_on_sale and bool(p.sale_price),
                'sale_price': sale_price_formatted,
                'image_b64': img_b64,
                'qr_b64': qr_b64,
                'wa_url': wa_url,
                'category_name': 'Piezas Especiales',
            })
        if orphan_items:
            total_products_count += len(orphan_items)
            for i in range(0, len(orphan_items), chunk_size):
                pages.append({
                    'category_name': 'Piezas Especiales',
                    'products': orphan_items[i:i + chunk_size]
                })

    return {
        'category_name': display_title,
        'category_subtitle': display_subtitle,
        'category_description': display_description,
        'is_holiday': is_holiday,
        'pages': pages,
        'total_products': total_products_count,
        'logo_b64': logo_b64,
        'hero_b64': fallback_img_b64,
        'current_year': datetime.now().year,
        'whatsapp_display': "660 904 515",
        'slogan': display_slogan,
        'location': "Lliçà d'Amunt (Barcelona, España)",
        'include_prices': bool(include_prices),
        'include_descriptions': bool(include_descriptions),
    }

def generate_catalog_pdf_bytes(
    category_slug=None,
    category_slugs=None,
    include_prices=True,
    include_descriptions=False,
    custom_title=None,
    custom_subtitle=None,
    custom_slogan=None,
    custom_description=None,
):
    """Genera el PDF del catálogo y devuelve (pdf_bytes, filename)."""
    context = build_catalog_context(
        category_slug=category_slug,
        category_slugs=category_slugs,
        include_prices=include_prices,
        include_descriptions=include_descriptions,
        custom_title=custom_title,
        custom_subtitle=custom_subtitle,
        custom_slogan=custom_slogan,
        custom_description=custom_description,
    )
    html_string = render_to_string('catalog_pdf.html', context)
    
    # Renderizar con WeasyPrint
    pdf_bytes = weasyprint.HTML(string=html_string).write_pdf()
    
    clean_cat = sanitize_filename(context['category_name'])
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"Catalogo_ProPrint3D_{clean_cat}_{date_str}.pdf"
    
    return pdf_bytes, filename

