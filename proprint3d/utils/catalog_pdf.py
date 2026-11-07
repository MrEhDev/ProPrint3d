import os
import io
import base64
import urllib.parse
import unicodedata
import re
import logging
from datetime import datetime
import qrcode
from PIL import Image
from django.conf import settings
from django.template.loader import render_to_string
import weasyprint

logger = logging.getLogger(__name__)

def generate_qr_base64(data_url):
    """Genera una imagen QR en formato data:image/png;base64."""
    try:
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
    except Exception as e:
        logger.warning(f"Error generando QR: {e}")
        return None

def get_optimized_image_base64(file_path_or_field, max_dim=400, quality=80):
    """
    Lee una imagen de disco o FieldFile, la redimensiona de forma eficiente
    y devuelve una cadena data:image/jpeg;base64,... ultraligera (20-40 KB).
    Evita desbordamientos de memoria (OOM) y bloqueos en WeasyPrint.
    """
    if not file_path_or_field:
        return None

    try:
        # Resolver ruta en disco
        file_path = None
        if hasattr(file_path_or_field, 'path') and file_path_or_field.name:
            try:
                if os.path.exists(file_path_or_field.path):
                    file_path = file_path_or_field.path
            except Exception:
                file_path = None
        elif isinstance(file_path_or_field, str) and os.path.exists(file_path_or_field):
            file_path = file_path_or_field

        if not file_path:
            return None

        with Image.open(file_path) as img:
            # Manejar transparencias / modos de color
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Redimensionar manteniendo proporción
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    except Exception as e:
        logger.warning(f"Error optimizando imagen para PDF ({file_path_or_field}): {e}")
        return None

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
    branch=None,
):
    """Construye el contexto de datos para la plantilla del catálogo PDF agrupando por categoría."""
    from proprint3d.models import Category, Product, Branch

    if not branch:
        branch = Branch.objects.filter(is_main=True, is_active=True).first()

    wa_phone = branch.whatsapp if branch else "34660904515"
    whatsapp_display = branch.display_phone_national if branch else "660 904 515"
    location = branch.display_location if branch else "Lliçà d'Amunt (Barcelona, España)"
    greeting = branch.greeting_name if branch else "ProPrint3D"

    static_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
    logo_path = os.path.join(static_dir, 'logo_square.png')
    hero_path = os.path.join(static_dir, 'hero_3d_render.png')

    # Imágenes optimizadas para reducir drásticamente el peso del PDF y evitar OOM
    logo_b64 = get_optimized_image_base64(logo_path, max_dim=240, quality=85) or get_optimized_image_base64(hero_path, max_dim=240, quality=80)
    hero_b64 = get_optimized_image_base64(hero_path, max_dim=500, quality=80) or logo_b64

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

    is_holiday = any('navidad' in (c.slug or '').lower() or 'navidad' in (c.name or '').lower() for c in selected_categories)

    # Sobrescrituras de portada si el admin las especificó
    display_title = custom_title.strip() if (custom_title and custom_title.strip()) else category_name
    display_subtitle = custom_subtitle.strip() if (custom_subtitle and custom_subtitle.strip()) else "Colección Exclusiva"
    display_slogan = custom_slogan.strip() if (custom_slogan and custom_slogan.strip()) else "Fabricado con calidad y precisión"
    display_description = custom_description.strip() if (custom_description and custom_description.strip()) else (
        category_description or "Piezas terminadas con tecnología FDM de alta definición, filamentos técnicos y revisión artesanal en cada pedido."
    )

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

            p_title = str(p.title or 'Pieza 3D')
            msg = f"Hola {greeting}, me interesa la pieza '{p_title}' del catálogo de {cat.name}."
            wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(msg)}"
            qr_b64 = generate_qr_base64(wa_url)

            # Imagen optimizada del producto (con fallback a hero_b64)
            img_b64 = get_optimized_image_base64(p.main_image, max_dim=400, quality=80) or hero_b64

            p_price = float(p.price) if p.price is not None else 0.0
            price_formatted = f"{p_price:.2f}".replace('.', ',') + " €"
            
            sale_price_formatted = None
            if p.sale_price is not None:
                try:
                    s_price = float(p.sale_price)
                    sale_price_formatted = f"{s_price:.2f}".replace('.', ',') + " €"
                except (ValueError, TypeError):
                    sale_price_formatted = None

            desc_text = (p.description or '').strip()
            # En tarjeta horizontal hay ancho generoso (hasta 220 caracteres sin desbordar)
            short_desc = desc_text[:220] + ('...' if len(desc_text) > 220 else '')

            cat_items.append({
                'id': p.id,
                'title': p_title,
                'dimensions': p.dimensions,
                'description': desc_text,
                'short_description': short_desc,
                'price': price_formatted,
                'is_on_sale': bool(p.is_on_sale and sale_price_formatted),
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

            p_title = str(p.title or 'Pieza 3D')
            msg = f"Hola {greeting}, me interesa la pieza '{p_title}' del catálogo."
            wa_url = f"https://wa.me/{wa_phone}?text={urllib.parse.quote(msg)}"
            qr_b64 = generate_qr_base64(wa_url)
            img_b64 = get_optimized_image_base64(p.main_image, max_dim=400, quality=80) or hero_b64

            p_price = float(p.price) if p.price is not None else 0.0
            price_formatted = f"{p_price:.2f}".replace('.', ',') + " €"

            sale_price_formatted = None
            if p.sale_price is not None:
                try:
                    s_price = float(p.sale_price)
                    sale_price_formatted = f"{s_price:.2f}".replace('.', ',') + " €"
                except (ValueError, TypeError):
                    sale_price_formatted = None

            desc_text = (p.description or '').strip()
            short_desc = desc_text[:220] + ('...' if len(desc_text) > 220 else '')

            orphan_items.append({
                'id': p.id,
                'title': p_title,
                'dimensions': p.dimensions,
                'description': desc_text,
                'short_description': short_desc,
                'price': price_formatted,
                'is_on_sale': bool(p.is_on_sale and sale_price_formatted),
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
        'hero_b64': hero_b64,
        'current_year': datetime.now().year,
        'whatsapp_display': whatsapp_display,
        'slogan': display_slogan,
        'location': location,
        'branch': branch,
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
    branch=None,
):
    """Genera el PDF del catálogo de manera eficiente y devuelve (pdf_bytes, filename)."""
    context = build_catalog_context(
        category_slug=category_slug,
        category_slugs=category_slugs,
        include_prices=include_prices,
        include_descriptions=include_descriptions,
        custom_title=custom_title,
        custom_subtitle=custom_subtitle,
        custom_slogan=custom_slogan,
        custom_description=custom_description,
        branch=branch,
    )
    html_string = render_to_string('catalog_pdf.html', context)
    
    # Renderizar con WeasyPrint pasando base_url seguro
    pdf_bytes = weasyprint.HTML(
        string=html_string,
        base_url=str(settings.BASE_DIR)
    ).write_pdf()
    
    clean_cat = sanitize_filename(context['category_name'])
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"Catalogo_ProPrint3D_{clean_cat}_{date_str}.pdf"
    
    return pdf_bytes, filename
