import io
import decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.db.models import Q

from functools import wraps
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def staff_member_required(view_func):
    """
    Decorador que asegura que el usuario sea staff.
    Si no está autenticado o no es staff, redirige al login personalizado con su parámetro next.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.is_staff):
            path = request.get_full_path()
            return redirect(f"{reverse('admin_login')}?next={path}")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Utilidades PDF
import io

from .models import Category, Product, Quote, QuoteItem, Order, OrderItem, ProductImage, Review, Cart, CartItem, Customer
from .forms import CalculatorForm, ProductFromCalcForm, ScraperForm, QuoteForm
from .utils.calculator import calculate_print_costs
from .utils.scraper import scrape_makerworld
from .utils.correos_rates import (
    calculate_all_correos_options,
    calculate_correos_rate,
    CORREOS_SERVICES,
    PACKAGING_TARE_DEFAULT_GRAMS
)

# =====================================================================
# VISTAS DE AUTENTICACIÓN ADMIN INTEGRADA
# =====================================================================
def admin_login_view(request):
    """
    Inicio de sesión de administradores con el estilo y diseño visual de ProPrint3D.
    Si ya está logueado como staff, redirige directamente al destino o al CRM.
    """
    next_url = request.GET.get('next') or request.POST.get('next') or reverse('crm_dashboard')
    
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(next_url)
        
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect(next_url)
            else:
                error = "Tu cuenta no tiene privilegios de administración del taller."
        else:
            error = "Usuario o contraseña incorrectos. Verifica tus credenciales."
            
    return render(request, 'admin_login.html', {'error': error, 'next': next_url})

def admin_logout_view(request):
    """Cierra la sesión del administrador y vuelve al catálogo."""
    logout(request)
    return redirect('catalog')

# =====================================================================
# VISTA: catalog_view
# Propósito: Mostrar el catálogo público a los clientes.
# =====================================================================
def catalog_view(request):
    """Renderiza la vista principal pública con productos, filtros y paginación."""
    category_slug = request.GET.get('category', '').strip()
    search_query = request.GET.get('q', '').strip()
    
    # Manejo de productos activos vs ocultos:
    # Los artículos ocultos (is_active=False) NUNCA se muestran en el catálogo normal,
    # solo en la pestaña exclusiva de categoría 'ocultos' para administradores.
    if category_slug == 'ocultos' and request.user.is_staff:
        products_qs = Product.objects.filter(is_active=False).prefetch_related('categories').order_by('-created_at')
    else:
        products_qs = Product.objects.filter(is_active=True).prefetch_related('categories').order_by('-created_at')
        
    categories = Category.objects.all()
    
    # Manejo de búsqueda por texto
    if search_query:
        products_qs = products_qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
        
    # Filtro por categoría
    if category_slug:
        if category_slug == 'ofertas':
            products_qs = products_qs.filter(is_on_sale=True)
        elif category_slug == 'ocultos':
            # Ya filtrado arriba
            pass
        else:
            products_qs = products_qs.filter(categories__slug=category_slug).distinct()
        
    # Conteo de productos ocultos para el badge de administración
    hidden_count = Product.objects.filter(is_active=False).count() if request.user.is_staff else 0

    # Paginación a 10 filas (en grid de 4 columnas en desktop = 40 piezas por página)
    paginator = Paginator(products_qs, 40)
    page_number = request.GET.get('page')
    try:
        products = paginator.page(page_number)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    context = {
        'products': products,
        'categories': categories,
        'search_query': search_query,
        'category_slug': category_slug,
        'hidden_count': hidden_count,
        'reviews': Review.objects.filter(is_active=True).order_by('-created_at')[:10],
    }
    return render(request, 'catalog.html', context)


# =====================================================================
# VISTA: product_detail_view
# Propósito: Mostrar el detalle de un producto específico.
# =====================================================================

def custom_order_view(request):
    """Muestra el formulario para pedir una pieza personalizada por WhatsApp."""
    return render(request, 'custom_order.html')

def about_view(request):
    """Muestra la página de '¿Quiénes somos?' con información del taller y tecnología."""
    return render(request, 'about.html')
def product_detail_view(request, slug):
    """Muestra detalles extendidos de una pieza del catálogo."""
    # Admins pueden ver productos ocultos (is_active=False)
    if request.user.is_staff:
        product = get_object_or_404(Product.objects.prefetch_related('categories'), slug=slug)
    else:
        product = get_object_or_404(Product.objects.prefetch_related('categories'), slug=slug, is_active=True)
        
    related_products = []
    if product.categories.exists():
        related_products = Product.objects.filter(
            categories__in=product.categories.all(), 
            is_active=True
        ).exclude(id=product.id).distinct().order_by('?')[:5]
    
    absolute_url = request.build_absolute_uri()
    wa_message = f"Hola ProPrint3d, estoy interesado en la pieza: {product.title}\n\n {absolute_url}"
    import urllib.parse
    wa_url = f"https://wa.me/34660904515?text={urllib.parse.quote(wa_message)}"
    
    context = {
        'product': product,
        'wa_url': wa_url,
        'related_products': related_products
    }
    return render(request, 'product_detail.html', context)

# =====================================================================
# VISTA: product_edit_view
# Propósito: Permite al admin editar un producto desde el frontend.
# =====================================================================
@staff_member_required
def product_edit_view(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    if request.method == 'POST':
        form = ProductFromCalcForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            product.save()
            form.save_m2m()
            
            new_category_str = form.cleaned_data.get('new_category', '')
            if new_category_str:
                names = [c.strip() for c in new_category_str.split(',') if c.strip()]
                for name in names:
                    cat, _ = Category.objects.get_or_create(name=name)
                    product.categories.add(cat)
            
            # Manejar nuevas imágenes
            gallery_images = request.FILES.getlist('gallery_images')
            for idx, img in enumerate(gallery_images):
                ProductImage.objects.create(
                    product=product,
                    image=img,
                    is_cover=False
                )
            
            return redirect('product_detail', slug=product.slug)
    else:
        form = ProductFromCalcForm(instance=product)
        
    return render(request, 'product_edit.html', {'form': form, 'product': product})

# =====================================================================
# VISTA: admin_dashboard_view
# Propósito: Panel de administración para gestión de costes y scraping.
# NOTA: Protegido con @staff_member_required
# =====================================================================
@staff_member_required
def admin_dashboard_view(request):
    """
    Controlador principal del Dashboard de herramientas internas.
    Maneja tanto la petición GET (mostrar forms vacíos) como
    la POST de la calculadora para procesar costes.
    """
    calc_form = CalculatorForm(request.POST or None)
    scraper_form = ScraperForm(request.POST or None)
    product_form = ProductFromCalcForm()
    
    calculation_result = None
    scraped_data = None
    
    if request.method == 'POST':
        # Acción 1: Calcular Costes
        if 'calculate_costs' in request.POST and calc_form.is_valid():
            w = calc_form.cleaned_data['weight_grams']
            h = calc_form.cleaned_data['hours']
            m = calc_form.cleaned_data['minutes']
            other = calc_form.cleaned_data['other_materials_cost']
            
            calculation_result = calculate_print_costs(w, h, m, other)
            time_decimal = h + (m/60)
            product_form = ProductFromCalcForm(initial={
                'weight_grams': w,
                'print_time_hours': round(time_decimal, 2),
                'price': calculation_result['suggested_prices']['x2_5'] # default
            })
            
        # Acción 2: Scraping MakerWorld
        elif 'scrape_url' in request.POST and scraper_form.is_valid():
            url = scraper_form.cleaned_data['url']
            scraped_data = scrape_makerworld(url)
            
            if scraped_data.get('success'):
                initial_data = {
                    'title': scraped_data['title'],
                    'description': scraped_data['description'],
                    'makerworld_url': url
                }
                if scraped_data.get('weight_grams'):
                    initial_data['weight_grams'] = scraped_data['weight_grams']
                if scraped_data.get('print_time_hours') is not None:
                    initial_data['print_time_hours'] = scraped_data['print_time_hours']
                if scraped_data.get('print_time_minutes') is not None:
                    initial_data['print_time_minutes'] = scraped_data['print_time_minutes']
                    
                product_form = ProductFromCalcForm(initial=initial_data)
                
        # Acción 3: Guardar nuevo Producto desde el Dashboard
        elif 'save_product' in request.POST:
            product_form_post = ProductFromCalcForm(request.POST, request.FILES)
            if product_form_post.is_valid():
                product = product_form_post.save(commit=False)
                product.save()
                product_form_post.save_m2m()
                
                new_category_str = product_form_post.cleaned_data.get('new_category', '')
                if new_category_str:
                    names = [c.strip() for c in new_category_str.split(',') if c.strip()]
                    for name in names:
                        cat, _ = Category.objects.get_or_create(name=name)
                        product.categories.add(cat)
                
                # Manejar múltiples imágenes para ProductImage
                gallery_images = request.FILES.getlist('gallery_images')
                for idx, img in enumerate(gallery_images):
                    ProductImage.objects.create(
                        product=product,
                        image=img,
                        is_cover=(idx == 0 and not product.main_image)
                    )
                    
                return redirect('admin_dashboard')
            else:
                product_form = product_form_post

    context = {
        'calc_form': calc_form,
        'scraper_form': scraper_form,
        'product_form': product_form,
        'calculation_result': calculation_result,
        'scraped_data': scraped_data,
    }
    return render(request, 'admin_dashboard.html', context)

# =====================================================================
# VISTA: quote_builder_view
# Propósito: Interfaz para construir un presupuesto paso a paso.
# =====================================================================
@staff_member_required
def quote_builder_view(request):
    """
    Vista para crear un nuevo presupuesto o añadir items a uno borrador.
    """
    if request.method == 'POST':
        quote_form = QuoteForm(request.POST)
        if quote_form.is_valid():
            quote = quote_form.save(commit=False)
            quote.status = 'Draft'
            quote.save()
            
            # Procesar Items dinámicos
            import json
            items_json = request.POST.get('items_json', '[]')
            try:
                items_data = json.loads(items_json)
                for item_data in items_data:
                    # product_id, title, unit_price, quantity
                    title = item_data['title']
                    product = Product.objects.filter(title=title).first()
                    QuoteItem.objects.create(
                        quote=quote,
                        product=product,
                        custom_title=title,
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price']
                    )
            except Exception as e:
                pass
                
            quote.update_total() # Recalcular suma
            
            # Redirigir al generador PDF
            return redirect('generate_quote_pdf', quote_id=quote.id)
    else:
        quote_form = QuoteForm()
        
    context = {
        'quote_form': quote_form,
        'products': Product.objects.filter(is_active=True)
    }
    return render(request, 'quote_builder.html', context)



# =====================================================================
# VISTA: generate_quote_pdf_view
# Propósito: Exportar un presupuesto a WeasyPrint.
# =====================================================================
from django.template.loader import render_to_string
from weasyprint import HTML
import unicodedata
import re
import datetime

def get_quote_pdf_filename(client_name, date_val=None):
    """
    Genera el nombre de archivo con formato: Presupuesto_Nombre_AÑOMESDIA.pdf
    Ejemplo: Presupuesto_Juan_20261030.pdf
    """
    if not date_val:
        date_str = datetime.date.today().strftime('%Y%m%d')
    elif isinstance(date_val, (datetime.date, datetime.datetime)):
        date_str = date_val.strftime('%Y%m%d')
    else:
        try:
            date_str = datetime.date.fromisoformat(str(date_val)).strftime('%Y%m%d')
        except Exception:
            date_str = datetime.date.today().strftime('%Y%m%d')

    # Normalizar acentos a ASCII y sanitizar caracteres no válidos en filenames
    normalized = unicodedata.normalize('NFKD', str(client_name or '')).encode('ASCII', 'ignore').decode('utf-8')
    clean_name = re.sub(r'[^\w\-]', '_', normalized).strip('_')
    clean_name = re.sub(r'_+', '_', clean_name)
    if not clean_name:
        clean_name = 'Cliente'

    return f"Presupuesto_{clean_name}_{date_str}.pdf"

def generate_quote_pdf_view(request, quote_id):
    """
    Busca el presupuesto, genera un PDF en memoria usando una plantilla HTML
    y lo devuelve como archivo descargable con el nombre: Presupuesto_Nombre_AÑOMESDIA.pdf
    """
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Generar el HTML
    context = {
        'quote': quote,
        'request': request,
    }
    html_string = render_to_string('quote_pdf.html', context)
    
    # Crear PDF con WeasyPrint
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    
    filename = get_quote_pdf_filename(quote.client_name, quote.created_at)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@staff_member_required
def generate_order_quote_pdf_view(request, order_id):
    """
    Genera el PDF del presupuesto directamente desde los detalles de un Pedido (Order) del CRM.
    Nombre de archivo: Presupuesto_Nombre_AÑOMESDIA.pdf (ej: Presupuesto_Juan_20261030.pdf)
    """
    order = get_object_or_404(Order.objects.prefetch_related('items', 'items__product'), id=order_id)
    
    items = []
    order_items = list(order.items.all())
    if order_items:
        for item in order_items:
            unit_price_val = float(item.unit_price or 0.00)
            qty_val = int(item.quantity or 1)
            line_price_val = float(item.price or (unit_price_val * qty_val))
            items.append({
                'custom_title': item.description or (item.product.title if item.product else 'Pieza a medida'),
                'product': item.product,
                'quantity': qty_val,
                'unit_price': f"{unit_price_val:.2f}",
                'calculated_cost': f"{line_price_val:.2f}",
                'dimensions': item.product.dimensions if (item.product and item.product.dimensions) else None
            })
    else:
        unit_price_val = float(order.unit_price or order.price or 0.00)
        qty_val = int(order.quantity or 1)
        line_price_val = float(order.price or (unit_price_val * qty_val))
        items.append({
            'custom_title': order.description or (order.product.title if order.product else 'Pieza a medida'),
            'product': order.product,
            'quantity': qty_val,
            'unit_price': f"{unit_price_val:.2f}",
            'calculated_cost': f"{line_price_val:.2f}",
            'dimensions': order.product.dimensions if (order.product and order.product.dimensions) else None
        })

    total_val = float(order.price or 0.00)
    include_tax = order.has_vat
    if include_tax:
        subtotal_val = round(total_val / 1.21, 2)
        tax_amount_val = round(total_val - subtotal_val, 2)
        tax_name = "IVA incl."
        tax_percentage = 21.00
    else:
        subtotal_val = total_val
        tax_amount_val = 0.00
        tax_name = "Sin IVA"
        tax_percentage = 0.00

    quote_data = {
        'id': order.id,
        'client_name': order.client_name,
        'client_contact': order.client_contact or 'No especificado',
        'created_at': order.order_date or datetime.date.today(),
        'notes': order.notes,
        'items': items,
        'subtotal': f"{subtotal_val:.2f}",
        'include_tax': include_tax,
        'tax_name': tax_name,
        'tax_percentage': tax_percentage,
        'tax_amount': f"{tax_amount_val:.2f}",
        'total_price': f"{total_val:.2f}"
    }

    context = {
        'quote': quote_data,
        'order': order,
        'request': request,
    }
    
    html_string = render_to_string('quote_pdf.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    
    filename = get_quote_pdf_filename(order.client_name, order.order_date or datetime.date.today())
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# =====================================================================
# VISTA: crm_dashboard_view
# Propósito: Panel de control de pedidos para administradores.
# =====================================================================
from django.db.models import Sum, F, Count

import calendar
import datetime
from django.http import JsonResponse
import json

@staff_member_required
def crm_dashboard_view(request):
    """
    Muestra la lista de pedidos con filtro de período desde-hasta y buscador.
    """
    search_query = request.GET.get('q', '').strip()
    
    # Filtros de rango
    year_from = request.GET.get('year_from', '').strip()
    month_from = request.GET.get('month_from', '').strip()
    year_to = request.GET.get('year_to', '').strip()
    month_to = request.GET.get('month_to', '').strip()
    
    # Compatibilidad con parámetros simples antiguos
    if not year_from and request.GET.get('year'):
        year_from = request.GET.get('year').strip()
    if not month_from and request.GET.get('month'):
        month_from = request.GET.get('month').strip()
        
    orders = Order.objects.all().order_by('-order_date')
    
    date_from = None
    date_to = None
    
    if year_from:
        try:
            y_f = int(year_from)
            m_f = int(month_from) if month_from else 1
            date_from = datetime.date(y_f, m_f, 1)
        except ValueError:
            pass
            
    if year_to:
        try:
            y_t = int(year_to)
            m_t = int(month_to) if month_to else 12
            last_day = calendar.monthrange(y_t, m_t)[1]
            date_to = datetime.date(y_t, m_t, last_day)
        except ValueError:
            pass
    elif year_from and month_to:
        try:
            y_t = int(year_from)
            m_t = int(month_to)
            last_day = calendar.monthrange(y_t, m_t)[1]
            date_to = datetime.date(y_t, m_t, last_day)
        except ValueError:
            pass
    elif year_from and month_from and not year_to and not month_to:
        # Si sólo se especificó un mes y año concretos (desde = hasta)
        try:
            y_t = int(year_from)
            m_t = int(month_from)
            last_day = calendar.monthrange(y_t, m_t)[1]
            date_to = datetime.date(y_t, m_t, last_day)
        except ValueError:
            pass

    if date_from:
        orders = orders.filter(order_date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__lte=date_to)
        
    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(client_name__icontains=search_query) |
            Q(notes__icontains=search_query) |
            Q(platform__icontains=search_query) |
            Q(shipping__icontains=search_query) |
            Q(items__description__icontains=search_query)
        ).distinct()
            
    # Autocorrección transparente: si hay pedidos antiguos o creados sin piezas,
    # se genera automáticamente su OrderItem para que se muestren de inmediato en el Kanban.
    orders_without_items = Order.objects.annotate(item_count=Count('items')).filter(item_count=0).exclude(status='Cancelado')
    for ord_obj in orders_without_items:
        OrderItem.objects.create(
            order=ord_obj,
            product=ord_obj.product,
            description=ord_obj.description or (ord_obj.product.title if ord_obj.product else f"Pedido #{ord_obj.id}"),
            quantity=ord_obj.quantity or 1,
            weight_grams=ord_obj.weight_grams or 0.0,
            print_time_hours=ord_obj.print_time_hours or 0.0,
            print_time_minutes=ord_obj.print_time_minutes or 0,
            extra_costs=ord_obj.extra_costs or decimal.Decimal('0.00'),
            unit_cost=ord_obj.unit_cost or decimal.Decimal('0.00'),
            total_cost=ord_obj.total_cost or decimal.Decimal('0.00'),
            unit_price=ord_obj.unit_price or decimal.Decimal('0.00'),
            price=ord_obj.price or decimal.Decimal('0.00'),
            status=ord_obj.status or 'Presupuestado',
            notes=ord_obj.notes or ''
        )

    # Kanban: Pasos solicitados -> Presupuestado - En proceso - Realizado - Enviado - Entregado - Cobrado
    active_order_items = OrderItem.objects.select_related('order', 'product').exclude(order__status='Cancelado')
    if date_from:
        active_order_items = active_order_items.filter(order__order_date__gte=date_from)
    if date_to:
        active_order_items = active_order_items.filter(order__order_date__lte=date_to)
    if search_query:
        active_order_items = active_order_items.filter(
            Q(description__icontains=search_query) |
            Q(order__client_name__icontains=search_query) |
            Q(order__notes__icontains=search_query) |
            Q(order__platform__icontains=search_query) |
            Q(order__shipping__icontains=search_query) |
            Q(order__id__icontains=search_query)
        )

    kanban_columns = {}
    for col_status in ['Presupuestado', 'En proceso', 'Realizado', 'Enviado', 'Entregado', 'Cobrado']:
        col_items = active_order_items.filter(status=col_status)
        orders_map = {}
        for item in col_items:
            oid = item.order_id
            if oid not in orders_map:
                orders_map[oid] = {
                    'order': item.order,
                    'items': [],
                    'total_items_in_order': item.order.items.count(),
                    'are_all_items_realizado': item.order.are_all_items_realizado,
                    'is_all_completed': item.order.is_all_completed,
                    'group_price': 0,
                    'group_cost': 0,
                    'group_weight': 0,
                }
            orders_map[oid]['items'].append(item)
            orders_map[oid]['group_price'] += float(item.price or 0)
            orders_map[oid]['group_cost'] += float(item.total_cost or 0)
            orders_map[oid]['group_weight'] += float(item.weight_grams or 0)
            item_mins = ((item.print_time_hours or 0.0) * 60 + (item.print_time_minutes or 0)) * item.remaining_quantity
            orders_map[oid]['group_print_minutes'] = orders_map[oid].get('group_print_minutes', 0) + item_mins

        card_groups = []
        for oid, data in orders_map.items():
            data['all_items_in_this_col'] = (len(data['items']) == data['total_items_in_order'])
            if data['order'].has_vat:
                if data['all_items_in_this_col']:
                    data['group_price'] = float(data['order'].price or 0)
                else:
                    data['group_price'] = round(data['group_price'] * 1.21, 2)
            
            # Cómputo exacto de tiempo de impresión solo de las piezas en esta columna (incluye días si >= 24h)
            mins = data.get('group_print_minutes', 0)
            data['group_print_hours'] = round(mins / 60.0, 2)
            mins_int = int(round(mins))
            h = int(mins_int // 60)
            m = int(mins_int % 60)
            h_str = f"{h}h {m}m" if m > 0 else f"{h}h"
            if h >= 24:
                days = h // 24
                dh = h % 24
                d_parts = [f"{days}d"]
                if dh > 0:
                    d_parts.append(f"{dh}h")
                if m > 0:
                    d_parts.append(f"{m}m")
                data['group_print_time_str'] = f"{h_str} ({' '.join(d_parts)})"
            else:
                data['group_print_time_str'] = h_str if mins_int > 0 else "0h"
            card_groups.append(data)
            
        kanban_columns[col_status] = card_groups

    # Tabla Desglose: Una fila por cada Pedido con acordeón desplegable de sus piezas
    orders = orders.prefetch_related('items', 'items__product').order_by('-order_date', '-id')

    # Cálculos globales sobre pedidos activos
    orders_for_stats = orders.exclude(status='Cancelado')
    totals = orders_for_stats.aggregate(
        total_sales=Sum('price'),
        total_costs=Sum('total_cost')
    )
    
    total_sales = totals['total_sales'] or 0
    total_costs = totals['total_costs'] or 0
    total_profit = total_sales - total_costs
    
    avg_profit = 0
    if orders_for_stats.count() > 0:
        avg_profit = total_profit / orders_for_stats.count()

    # Métricas de tiempo de taller y eficiencia horaria
    total_stats_hours = sum(o.total_print_time_hours for o in orders_for_stats)
    avg_hourly_rate = (float(total_profit) / total_stats_hours) if total_stats_hours > 0 else 0.0

    # Pedidos en cola activa (Presupuestado y En proceso)
    # Sumar únicamente las piezas que siguen pendientes en estas columnas
    queue_items = active_order_items.filter(status__in=['Presupuestado', 'En proceso'])
    queue_mins = sum(((i.print_time_hours or 0.0) * 60 + (i.print_time_minutes or 0)) * (i.quantity or 1) for i in queue_items)
    queue_hours = round(queue_mins / 60.0, 2)

    # Recuento inicial de pedidos urgentes / con fecha límite próxima
    urgent_orders_count = sum(1 for o in orders if o.deadline_info and o.deadline_info.get('is_urgent'))
        
    products_qs = Product.objects.filter(is_active=True).prefetch_related('categories')
    products_with_id = []
    for p in products_qs:
        products_with_id.append({
            'id': p.id,
            'title': p.title,
            'price': float(p.price),
            'sale_price': float(p.sale_price) if p.sale_price else None,
            'is_on_sale': p.is_on_sale,
            'weight_grams': p.weight_grams or 0.0,
            'print_time_hours': p.print_time_hours or 0.0,
            'print_time_minutes': p.print_time_minutes or 0,
            'extra_costs': float(p.extra_costs or 0.0),
            'image_url': p.main_image.url if p.main_image else None,
            'category_name': p.category_names or 'Catálogo'
        })

    context = {
        'orders': orders,
        'kanban_columns': kanban_columns,
        'search_query': search_query,
        'year_from': year_from,
        'month_from': month_from,
        'year_to': year_to,
        'month_to': month_to,
        'total_sales': total_sales,
        'total_costs': total_costs,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
        'avg_hourly_rate': avg_hourly_rate,
        'queue_hours': queue_hours,
        'urgent_orders_count': urgent_orders_count,
        'payment_methods': [c[0] for c in Order.PAYMENT_METHOD_CHOICES],
        'status_choices': [c[0] for c in Order.STATUS_CHOICES],
        'platform_choices': Order.PLATFORM_CHOICES,
        'shipping_choices': Order.SHIPPING_CHOICES,
        'correos_services': CORREOS_SERVICES,
        'customers': Customer.objects.all().order_by('-updated_at')[:50],
        'products_with_id': products_with_id,
        'products_json': json.dumps(products_with_id, default=str),
    }
    
    return render(request, 'crm_dashboard.html', context)

@staff_member_required
def update_order_status_api(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            order = Order.objects.get(id=order_id)
            if new_status in [s[0] for s in Order.STATUS_CHOICES]:
                order.status = new_status
                order.update_status_dates(new_status)
                order.save()
                # Sincronizar todas las piezas del pedido a este nuevo estado
                order.items.all().update(status=new_status)
                return JsonResponse({
                    'success': True,
                    'status': order.status,
                    'shipped_date': order.shipped_date.strftime('%d/%m/%Y') if order.shipped_date else None,
                    'delivered_date': order.delivered_date.strftime('%d/%m/%Y') if order.delivered_date else None,
                    'paid_date': order.paid_date.strftime('%d/%m/%Y') if order.paid_date else None,
                })
            return JsonResponse({'success': False, 'error': 'Estado inválido'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@staff_member_required
def update_item_status_api(request, item_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            item = OrderItem.objects.select_related('order').get(id=item_id)
            if new_status in [s[0] for s in Order.STATUS_CHOICES]:
                item.status = new_status
                item.save()
                order = item.order
                
                order_items = list(order.items.all())
                all_realizado = all(i.status == 'Realizado' for i in order_items)
                
                # Si se mueve a fases globales de envío/entrega/cobro
                if new_status in ['Enviado', 'Entregado', 'Cobrado']:
                    order.status = new_status
                    order.update_status_dates(new_status)
                    order.save()
                    order.items.all().update(status=new_status)
                elif all_realizado:
                    order.status = 'Realizado'
                    order.update_status_dates('Realizado')
                    order.save()
                elif any(i.status == 'En proceso' for i in order_items):
                    if order.status == 'Presupuestado':
                        order.status = 'En proceso'
                        order.save()
                elif all(i.status == 'Presupuestado' for i in order_items):
                    order.status = 'Presupuestado'
                    order.save()

                return JsonResponse({
                    'success': True,
                    'item_id': item.id,
                    'item_status': item.status,
                    'order_id': order.id,
                    'order_status': order.status,
                    'are_all_items_realizado': order.are_all_items_realizado
                })
            return JsonResponse({'success': False, 'error': 'Estado inválido'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@staff_member_required
def update_item_cost_api(request, item_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_cost = data.get('cost')
            item = OrderItem.objects.select_related('order').get(id=item_id)
            if new_cost is not None:
                import decimal
                cleaned_cost = str(new_cost).strip().replace(',', '.')
                if cleaned_cost:
                    item.total_cost = decimal.Decimal(cleaned_cost)
                    if item.quantity and item.quantity > 0:
                        item.unit_cost = item.total_cost / decimal.Decimal(str(item.quantity))
                    item.save()
                    item.order.update_totals_from_items()
                    return JsonResponse({'success': True, 'total_cost': str(item.total_cost)})
            return JsonResponse({'success': False, 'error': 'Coste inválido'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@staff_member_required
def update_item_progress_api(request, item_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item = OrderItem.objects.select_related('order').get(id=item_id)
            delta = data.get('delta')
            set_val = data.get('completed_quantity')
            
            total_qty = item.quantity or 1
            if delta is not None:
                new_completed = (item.completed_quantity or 0) + int(delta)
            elif set_val is not None:
                new_completed = int(set_val)
            else:
                return JsonResponse({'success': False, 'error': 'Valor no especificado'})
            
            # Limitar entre 0 y total_qty
            item.completed_quantity = max(0, min(total_qty, new_completed))
            item.save()

            order = item.order
            all_order_items = list(order.items.all())
            all_items_completed = all((i.completed_quantity or 0) >= (i.quantity or 1) for i in all_order_items)

            return JsonResponse({
                'success': True,
                'item_id': item.id,
                'order_id': order.id,
                'completed_quantity': item.completed_quantity,
                'total_quantity': total_qty,
                'remaining_quantity': item.remaining_quantity,
                'is_item_fully_completed': (item.completed_quantity >= total_qty),
                'all_items_completed': all_items_completed,
                'remaining_print_time_hours': item.remaining_print_time_hours,
                'remaining_print_time_str': item.remaining_print_time_str,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@staff_member_required
def update_order_dates_api(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order = Order.objects.get(id=order_id)
            def parse_date(val):
                if val:
                    return datetime.date.fromisoformat(val)
                return None
            
            if 'shipped_date' in data:
                order.shipped_date = parse_date(data['shipped_date'])
            if 'delivered_date' in data:
                order.delivered_date = parse_date(data['delivered_date'])
            if 'paid_date' in data:
                order.paid_date = parse_date(data['paid_date'])
            if 'deadline' in data:
                order.deadline = parse_date(data['deadline'])
                
            order.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@staff_member_required
def update_order_payment_api(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order = Order.objects.get(id=order_id)
            
            # Actualizar estado si se indica (por ejemplo al cobrar)
            new_status = data.get('status')
            if new_status and new_status in dict(Order.STATUS_CHOICES):
                order.status = new_status
                order.update_status_dates(new_status)
                # Cascada a todas sus piezas
                order.items.all().update(status=new_status)
            
            # Datos de pagos
            if 'deposit_amount' in data:
                try:
                    raw_dep = str(data['deposit_amount']).strip().replace(',', '.')
                    order.deposit_amount = decimal.Decimal(raw_dep) if raw_dep else decimal.Decimal('0.00')
                except Exception:
                    pass
            if 'deposit_method' in data:
                order.deposit_method = data.get('deposit_method') or ''
            if 'final_payment_method' in data:
                order.final_payment_method = data.get('final_payment_method') or ''
            if 'payment_notes' in data:
                order.payment_notes = data.get('payment_notes') or ''
                
            order.save()
            
            return JsonResponse({
                'success': True,
                'status': order.status,
                'deposit_amount': float(order.deposit_amount or 0),
                'deposit_method': order.deposit_method or '',
                'final_payment_method': order.final_payment_method or '',
                'remaining_amount': float(order.remaining_amount),
                'payment_summary': order.payment_summary_text,
                'paid_date': order.paid_date.strftime('%d/%m/%Y') if order.paid_date else ''
            })
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Pedido no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@staff_member_required
def update_order_full_api(request, order_id):
    """
    Actualiza completamente un pedido y su desglose de piezas (añadir, editar o eliminar piezas).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order = get_object_or_404(Order, id=order_id)
            
            # 1. Cabecera del pedido
            if 'client_name' in data and data['client_name'].strip():
                order.client_name = data['client_name'].strip()
            if 'client_phone' in data:
                order.client_phone = data['client_phone'].strip() if data['client_phone'] else ''
            if 'client_email' in data:
                order.client_email = data['client_email'].strip() if data['client_email'] else ''
            if 'client_contact' in data:
                order.client_contact = data['client_contact'].strip() if data['client_contact'] else ''
            if not order.client_contact and (order.client_phone or order.client_email):
                parts = [p for p in [order.client_phone, order.client_email] if p]
                order.client_contact = " · ".join(parts)
            if 'include_shipping_in_total' in data:
                order.include_shipping_in_total = bool(data['include_shipping_in_total'])
            
            # Cliente habitual / recurrente
            customer_id = data.get('customer_id')
            if customer_id:
                order.customer = Customer.objects.filter(id=customer_id).first()
            elif 'customer_id' in data and data['customer_id'] is None:
                order.customer = None
                
            # Datos de dirección postal
            if 'shipping_address' in data:
                order.shipping_address = data['shipping_address'].strip() if data['shipping_address'] else ''
            if 'shipping_postal_code' in data:
                order.shipping_postal_code = data['shipping_postal_code'].strip() if data['shipping_postal_code'] else ''
            if 'shipping_city' in data:
                order.shipping_city = data['shipping_city'].strip() if data['shipping_city'] else ''
            if 'shipping_province' in data:
                order.shipping_province = data['shipping_province'].strip() if data['shipping_province'] else ''
                
            # Logística Correos
            if 'correos_service' in data:
                order.correos_service = data['correos_service'].strip() if data['correos_service'] else 'carta_certificada'
            if 'correos_tracking_number' in data:
                order.correos_tracking_number = data['correos_tracking_number'].strip() if data['correos_tracking_number'] else ''
            if 'shipping_cost_paid_by' in data:
                order.shipping_cost_paid_by = data['shipping_cost_paid_by']
            if 'shipping_cost_estimated' in data:
                try:
                    order.shipping_cost_estimated = decimal.Decimal(str(data['shipping_cost_estimated']).replace(',', '.'))
                except Exception:
                    pass
            if 'shipping_weight_grams' in data:
                try:
                    order.shipping_weight_grams = float(data['shipping_weight_grams']) if data['shipping_weight_grams'] is not None else None
                except (ValueError, TypeError):
                    pass
            if 'shipping_pkg_length' in data:
                try:
                    order.shipping_pkg_length = float(data['shipping_pkg_length']) if data['shipping_pkg_length'] else None
                except (ValueError, TypeError):
                    pass
            if 'shipping_pkg_width' in data:
                try:
                    order.shipping_pkg_width = float(data['shipping_pkg_width']) if data['shipping_pkg_width'] else None
                except (ValueError, TypeError):
                    pass
            if 'shipping_pkg_height' in data:
                try:
                    order.shipping_pkg_height = float(data['shipping_pkg_height']) if data['shipping_pkg_height'] else None
                except (ValueError, TypeError):
                    pass

            # Guardar / actualizar en base de datos de Clientes si se solicita
            if data.get('save_as_customer'):
                cust = order.customer
                if not cust and order.client_name:
                    cust = Customer.objects.filter(name__iexact=order.client_name).first()
                if not cust:
                    cust = Customer(name=order.client_name)
                
                # Actualizar campos de contacto y envío en la ficha de cliente
                cust.name = order.client_name
                if order.client_phone:
                    cust.phone = order.client_phone
                if order.client_email:
                    cust.email = order.client_email
                elif order.client_contact:
                    if '@' in order.client_contact:
                        cust.email = order.client_contact
                    else:
                        cust.phone = order.client_contact
                if order.shipping_address:
                    cust.address = order.shipping_address
                if order.shipping_postal_code:
                    cust.postal_code = order.shipping_postal_code
                if order.shipping_city:
                    cust.city = order.shipping_city
                if order.shipping_province:
                    cust.province = order.shipping_province
                cust.save()
                order.customer = cust

            if 'order_date' in data and data['order_date']:
                order.order_date = datetime.date.fromisoformat(data['order_date'])
            if 'deadline' in data:
                order.deadline = datetime.date.fromisoformat(data['deadline']) if data['deadline'] else None
            if 'platform' in data:
                order.platform = data['platform']
            if 'shipping' in data:
                order.shipping = data['shipping']
            if 'notes' in data:
                order.notes = data['notes']
            if 'status' in data and data['status'] in dict(Order.STATUS_CHOICES):
                order.status = data['status']
                order.update_status_dates(order.status)
            if 'has_vat' in data:
                order.has_vat = bool(data['has_vat'])
            if 'has_irpf' in data:
                order.has_irpf = bool(data['has_irpf'])
            order.save()
                
            # 2. Piezas del pedido
            pieces = data.get('pieces', [])
            if not pieces:
                return JsonResponse({'success': False, 'error': 'El pedido debe contener al menos una pieza.'}, status=400)
                
            existing_items_map = {item.id: item for item in order.items.all()}
            retained_ids = set()
            
            for p in pieces:
                pid = p.get('id')
                product_id = p.get('product_id')
                product = Product.objects.filter(id=product_id).first() if product_id else None
                desc = p.get('description', '').strip() or (product.title if product else 'Pieza a medida')
                qty = int(p.get('quantity') or 1)
                w = float(p.get('weight_grams') or 0.0)
                h = float(p.get('print_time_hours') or 0.0)
                m = int(p.get('print_time_minutes') or 0)
                extra = decimal.Decimal(str(p.get('extra_costs') or 0.00).replace(',', '.'))
                u_cost = decimal.Decimal(str(p.get('unit_cost') or 0.00).replace(',', '.'))
                t_cost = decimal.Decimal(str(p.get('total_cost') or 0.00).replace(',', '.'))
                u_price = decimal.Decimal(str(p.get('unit_price') or 0.00).replace(',', '.'))
                t_price = decimal.Decimal(str(p.get('price') or 0.00).replace(',', '.'))
                status_piece = p.get('status') or order.status
                notes_piece = p.get('notes', '').strip() if p.get('notes') else ''
                
                if pid and int(pid) in existing_items_map:
                    itm = existing_items_map[int(pid)]
                    itm.product = product
                    itm.description = desc
                    itm.quantity = qty
                    itm.weight_grams = w
                    itm.print_time_hours = h
                    itm.print_time_minutes = m
                    itm.extra_costs = extra
                    itm.unit_cost = u_cost
                    itm.total_cost = t_cost
                    itm.unit_price = u_price
                    itm.price = t_price
                    itm.status = status_piece
                    itm.notes = notes_piece
                    itm.save()
                    retained_ids.add(itm.id)
                else:
                    new_itm = OrderItem.objects.create(
                        order=order,
                        product=product,
                        description=desc,
                        quantity=qty,
                        weight_grams=w,
                        print_time_hours=h,
                        print_time_minutes=m,
                        extra_costs=extra,
                        unit_cost=u_cost,
                        total_cost=t_cost,
                        unit_price=u_price,
                        price=t_price,
                        status=status_piece,
                        notes=notes_piece
                    )
                    retained_ids.add(new_itm.id)
                    
            # Eliminar piezas que se hayan borrado desde el modal
            to_delete = set(existing_items_map.keys()) - retained_ids
            if to_delete:
                OrderItem.objects.filter(id__in=to_delete, order=order).delete()
                
            # 3. Recalcular totales desde las piezas
            order.update_totals_from_items()
            
            # Ajustar estado consolidado del pedido según sus piezas
            all_piece_statuses = list(order.items.values_list('status', flat=True))
            if all(s == 'Cobrado' for s in all_piece_statuses):
                order.status = 'Cobrado'
            elif all(s in ['Cobrado', 'Entregado'] for s in all_piece_statuses):
                order.status = 'Entregado'
            elif all(s in ['Cobrado', 'Entregado', 'Enviado'] for s in all_piece_statuses):
                order.status = 'Enviado'
            elif all(s in ['Cobrado', 'Entregado', 'Enviado', 'Realizado'] for s in all_piece_statuses):
                order.status = 'Realizado'
            elif any(s in ['En proceso', 'Realizado', 'Enviado', 'Entregado', 'Cobrado'] for s in all_piece_statuses):
                if order.status == 'Presupuestado':
                    order.status = 'En proceso'
                    
            order.update_status_dates(order.status)
            order.save()
            
            return JsonResponse({'success': True, 'order_id': order.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@staff_member_required
def delete_order_api(request, order_id):
    """
    Elimina permanentemente un pedido y todas sus piezas asociadas.
    """
    if request.method == 'POST':
        try:
            order = get_object_or_404(Order, id=order_id)
            order.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@staff_member_required
def update_order_cost_api(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_cost = data.get('cost')
            order = Order.objects.get(id=order_id)
            if new_cost is not None:
                import decimal
                cleaned_cost = str(new_cost).strip().replace(',', '.')
                if cleaned_cost:
                    order.total_cost = decimal.Decimal(cleaned_cost)
                    if order.quantity and order.quantity > 0:
                        order.unit_cost = order.total_cost / decimal.Decimal(str(order.quantity))
                    order.save()
                    return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Coste inválido'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@staff_member_required
def check_product_title_api(request):
    """Verifica si un producto con este título ya existe."""
    title = request.GET.get('title', '')
    if not title:
        return JsonResponse({'exists': False})
    exists = Product.objects.filter(title__iexact=title).exists()
    return JsonResponse({'exists': exists})

@staff_member_required
def toggle_sale_api(request, slug):
    if request.method == 'POST':
        product = get_object_or_404(Product, slug=slug)
        product.is_on_sale = 'is_on_sale' in request.POST
        product.save()
        return redirect('product_detail', slug=slug)
    return redirect('catalog')

@staff_member_required
def toggle_active_api(request, slug):
    """Oculta o muestra un producto del catálogo público."""
    if request.method == 'POST':
        product = get_object_or_404(Product, slug=slug)
        product.is_active = not product.is_active
        product.save()
        return redirect('product_detail', slug=slug)
    return redirect('catalog')

@staff_member_required
def product_delete_view(request, slug):
    """Elimina permanentemente un producto."""
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        product.delete()
        return redirect('catalog')
    # GET: Mostrar confirmación si se accede directamente
    return redirect('product_detail', slug=slug)

@staff_member_required
def product_image_delete_api(request, image_id):
    """Elimina una imagen de galería."""
    if request.method == 'POST':
        img = get_object_or_404(ProductImage, id=image_id)
        product_slug = img.product.slug
        img.image.delete(save=False)
        img.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@staff_member_required
def get_product_price_api(request, product_id):
    """Devuelve el precio de un producto para el formulario de pedido."""
    try:
        product = Product.objects.get(id=product_id)
        price = float(product.sale_price if product.is_on_sale and product.sale_price else product.price)
        return JsonResponse({'success': True, 'price': price, 'title': product.title})
    except Product.DoesNotExist:
        return JsonResponse({'success': False})

from django import forms

class SmartOrderForm(forms.ModelForm):
    smart_product_name = forms.CharField(
        label="Producto o Descripción Libre",
        required=True,
        help_text="Selecciona del catálogo o escribe un nombre nuevo.",
        widget=forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white border-gray-300 dark:border-gray-700 focus:border-primary', 'list': 'products-datalist', 'placeholder': 'Escribe o selecciona del catálogo...'})
    )

    platform = forms.ChoiceField(
        choices=[('', 'Selecciona plataforma...')] + Order.PLATFORM_CHOICES,
        required=False,
        label="Plataforma",
        initial=''
    )

    shipping = forms.ChoiceField(
        choices=[('', 'Selecciona método de envío...')] + Order.SHIPPING_CHOICES,
        required=False,
        label="Método de Envío",
        initial=''
    )

    class Meta:
        model = Order
        fields = [
            'client_name', 'client_phone', 'client_email', 'client_contact', 'customer', 'order_date', 'deadline', 'status', 'quantity', 
            'weight_grams', 'print_time_hours', 'print_time_minutes', 'extra_costs',
            'unit_cost', 'total_cost', 'unit_price', 'price',
            'shipped_date', 'delivered_date', 'paid_date',
            'platform', 'shipping', 'notes',
            'has_vat', 'has_irpf',
            'deposit_amount', 'deposit_method', 'final_payment_method', 'payment_notes',
            'shipping_address', 'shipping_postal_code', 'shipping_city', 'shipping_province',
            'correos_service', 'tracking_number', 'shipping_cost', 'shipping_cost_paid_by',
            'shipping_package_weight', 'include_shipping_in_total'
        ]
        widgets = {
            'client_phone': forms.TextInput(attrs={'placeholder': 'Ej. 612 34 56 78'}),
            'client_email': forms.EmailInput(attrs={'placeholder': 'Ej. cliente@gmail.com'}),
            'client_contact': forms.TextInput(attrs={'placeholder': 'Email, teléfono o usuario de contacto'}),
            'shipping_address': forms.TextInput(attrs={'placeholder': 'Calle, número, piso, puerta...'}),
            'shipping_postal_code': forms.TextInput(attrs={'placeholder': 'Ej. 08186'}),
            'shipping_city': forms.TextInput(attrs={'placeholder': 'Ej. Lliçà d\'Amunt'}),
            'shipping_province': forms.TextInput(attrs={'placeholder': 'Ej. Barcelona'}),
            'tracking_number': forms.TextInput(attrs={'placeholder': 'Ej. PK012345678ES'}),
            'shipping_cost': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'shipping_package_weight': forms.NumberInput(attrs={'placeholder': '100'}),
            'order_date': forms.DateInput(attrs={'type': 'date'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'shipped_date': forms.DateInput(attrs={'type': 'date'}),
            'delivered_date': forms.DateInput(attrs={'type': 'date'}),
            'paid_date': forms.DateInput(attrs={'type': 'date'}),
            'deposit_amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'payment_notes': forms.TextInput(attrs={'placeholder': 'Ej. Pagado 20€ Bizum señal...'}),
            'weight_grams': forms.NumberInput(attrs={'step': 'any', 'placeholder': '0'}),
            'print_time_hours': forms.NumberInput(attrs={'step': 'any', 'placeholder': '0'}),
            'print_time_minutes': forms.NumberInput(attrs={'step': '1', 'min': '0', 'max': '59', 'placeholder': '0'}),
            'extra_costs': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'unit_cost': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'total_cost': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Color, material, detalles especiales...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client_contact'].required = False
        if 'client_phone' in self.fields:
            self.fields['client_phone'].required = False
        if 'client_email' in self.fields:
            self.fields['client_email'].required = False
        if 'include_shipping_in_total' in self.fields:
            self.fields['include_shipping_in_total'].required = False
        self.fields['price'].required = False
        self.fields['unit_price'].required = False
        self.fields['weight_grams'].required = False
        self.fields['print_time_hours'].required = False
        self.fields['print_time_minutes'].required = False
        self.fields['extra_costs'].required = False
        self.fields['unit_cost'].required = False
        self.fields['total_cost'].required = False
        self.fields['deadline'].required = False
        self.fields['shipped_date'].required = False
        self.fields['delivered_date'].required = False
        self.fields['paid_date'].required = False
        self.fields['notes'].required = False
        self.fields['deposit_amount'].required = False
        self.fields['deposit_method'].required = False
        self.fields['final_payment_method'].required = False
        self.fields['payment_notes'].required = False
        if 'customer' in self.fields:
            self.fields['customer'].required = False
        if 'shipping_address' in self.fields:
            self.fields['shipping_address'].required = False
        if 'shipping_postal_code' in self.fields:
            self.fields['shipping_postal_code'].required = False
        if 'shipping_city' in self.fields:
            self.fields['shipping_city'].required = False
        if 'shipping_province' in self.fields:
            self.fields['shipping_province'].required = False
        if 'correos_service' in self.fields:
            self.fields['correos_service'].required = False
        if 'tracking_number' in self.fields:
            self.fields['tracking_number'].required = False
        if 'shipping_cost' in self.fields:
            self.fields['shipping_cost'].required = False
        if 'shipping_cost_paid_by' in self.fields:
            self.fields['shipping_cost_paid_by'].required = False
        if 'shipping_package_weight' in self.fields:
            self.fields['shipping_package_weight'].required = False
        
        # Add Tailwind classes dynamically
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-input w-full rounded-md bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white border-gray-300 dark:border-gray-700 focus:border-primary'})

@staff_member_required
def order_create_view(request):
    import json
    import decimal

    if request.method == 'POST':
        pieces_json = request.POST.get('pieces_json', '').strip()
        client_name = request.POST.get('client_name', '').strip()
        client_phone = request.POST.get('client_phone', '').strip()
        client_email = request.POST.get('client_email', '').strip()
        client_contact = request.POST.get('client_contact', '').strip()
        if not client_contact:
            parts = [p for p in [client_phone, client_email] if p]
            if parts:
                client_contact = " · ".join(parts)
        order_date = request.POST.get('order_date')
        deadline = request.POST.get('deadline') or None
        platform = request.POST.get('platform', '').strip()
        shipping = request.POST.get('shipping', '').strip()
        notes = request.POST.get('notes', '').strip()
        include_shipping_in_total = request.POST.get('include_shipping_in_total') in ['true', 'on', '1', True]
        
        parsed_pieces = []
        if pieces_json:
            try:
                parsed_pieces = json.loads(pieces_json)
            except Exception:
                parsed_pieces = []
                
        initial_status = request.POST.get('status', 'Presupuestado').strip() or 'Presupuestado'
        if initial_status not in dict(Order.STATUS_CHOICES):
            initial_status = 'Presupuestado'

        has_vat = request.POST.get('has_vat') in ['true', 'on', '1', True]
        has_irpf = request.POST.get('has_irpf') in ['true', 'on', '1', True]

        raw_dep = request.POST.get('deposit_amount', '').strip().replace(',', '.')
        try:
            deposit_val = decimal.Decimal(raw_dep) if raw_dep else decimal.Decimal('0.00')
        except Exception:
            deposit_val = decimal.Decimal('0.00')
        deposit_method_val = request.POST.get('deposit_method', '').strip()
        final_payment_method_val = request.POST.get('final_payment_method', '').strip()
        payment_notes_val = request.POST.get('payment_notes', '').strip()

        # Cliente y logística
        customer_id = request.POST.get('customer_id', '').strip()
        customer = Customer.objects.filter(id=customer_id).first() if customer_id else None
        shipping_address = request.POST.get('shipping_address', '').strip()
        shipping_postal_code = request.POST.get('shipping_postal_code', '').strip()
        shipping_city = request.POST.get('shipping_city', '').strip()
        shipping_province = request.POST.get('shipping_province', '').strip()
        correos_service = request.POST.get('correos_service', 'carta_certificada').strip() or 'carta_certificada'
        correos_tracking = request.POST.get('correos_tracking_number', '').strip()
        shipping_cost_paid_by = request.POST.get('shipping_cost_paid_by', 'client').strip()
        
        raw_ship_cost = request.POST.get('shipping_cost_estimated', '').strip().replace(',', '.')
        try:
            ship_cost_val = decimal.Decimal(raw_ship_cost) if raw_ship_cost else decimal.Decimal('0.00')
        except Exception:
            ship_cost_val = decimal.Decimal('0.00')

        save_as_cust = request.POST.get('save_as_customer') in ['true', 'on', '1', True]
        if save_as_cust and client_name:
            if not customer:
                customer = Customer.objects.filter(name__iexact=client_name).first()
            if not customer:
                customer = Customer(name=client_name)
            customer.name = client_name
            if client_phone:
                customer.phone = client_phone
            if client_email:
                customer.email = client_email
            elif client_contact:
                if '@' in client_contact:
                    customer.email = client_contact
                else:
                    customer.phone = client_contact
            if shipping_address:
                customer.address = shipping_address
            if shipping_postal_code:
                customer.postal_code = shipping_postal_code
            if shipping_city:
                customer.city = shipping_city
            if shipping_province:
                customer.province = shipping_province
            customer.save()

        if client_name and order_date and parsed_pieces:
            order = Order.objects.create(
                client_name=client_name,
                client_contact=client_contact,
                client_phone=client_phone,
                client_email=client_email,
                customer=customer,
                order_date=order_date,
                deadline=deadline,
                platform=platform,
                shipping=shipping,
                shipping_address=shipping_address,
                shipping_postal_code=shipping_postal_code,
                shipping_city=shipping_city,
                shipping_province=shipping_province,
                correos_service=correos_service,
                tracking_number=correos_tracking,
                shipping_cost=ship_cost_val,
                shipping_cost_paid_by=shipping_cost_paid_by,
                include_shipping_in_total=include_shipping_in_total,
                notes=notes,
                status=initial_status,
                has_vat=has_vat,
                has_irpf=has_irpf,
                deposit_amount=deposit_val,
                deposit_method=deposit_method_val,
                final_payment_method=final_payment_method_val,
                payment_notes=payment_notes_val
            )
            
            for p in parsed_pieces:
                prod_id = p.get('product_id')
                product = None
                if prod_id:
                    try:
                        product = Product.objects.filter(id=int(prod_id)).first()
                    except (ValueError, TypeError):
                        product = None
                desc = p.get('description') or (product.title if product else 'Pieza a medida')
                if not product and desc:
                    product = Product.objects.filter(title__iexact=desc).first()
                
                qty = int(p.get('quantity') or 1)
                weight = float(p.get('weight_grams') or 0.0)
                h = float(p.get('print_time_hours') or 0.0)
                m = int(p.get('print_time_minutes') or 0)
                extra = decimal.Decimal(str(p.get('extra_costs') or 0.00).replace(',', '.'))
                u_cost = decimal.Decimal(str(p.get('unit_cost') or 0.00).replace(',', '.'))
                t_cost = decimal.Decimal(str(p.get('total_cost') or 0.00).replace(',', '.'))
                u_price = decimal.Decimal(str(p.get('unit_price') or 0.00).replace(',', '.'))
                t_price = decimal.Decimal(str(p.get('price') or 0.00).replace(',', '.'))
                
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    description=desc,
                    quantity=qty,
                    weight_grams=weight,
                    print_time_hours=h,
                    print_time_minutes=m,
                    extra_costs=extra,
                    unit_cost=u_cost,
                    total_cost=t_cost if t_cost > 0 else (u_cost * qty),
                    unit_price=u_price,
                    price=t_price if t_price > 0 else (u_price * qty),
                    status=initial_status,
                    notes=p.get('notes', '').strip() if p.get('notes') else ''
                )
                
            order.update_totals_from_items()
            return redirect('crm_dashboard')

        # Fallback a formulario tradicional SmartOrderForm
        form = SmartOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            smart_name = form.cleaned_data['smart_product_name']
            
            # Buscar si el nombre coincide con un producto
            product = Product.objects.filter(title__iexact=smart_name).first()
            if product:
                order.product = product
                order.description = product.title
            else:
                order.product = None
                order.description = smart_name
                
            order.deposit_amount = deposit_val
            order.deposit_method = deposit_method_val
            order.final_payment_method = final_payment_method_val
            order.payment_notes = payment_notes_val
            order.has_vat = has_vat
            order.has_irpf = has_irpf
            if client_phone:
                order.client_phone = client_phone
            if client_email:
                order.client_email = client_email
            if client_contact:
                order.client_contact = client_contact
            order.include_shipping_in_total = include_shipping_in_total
            order.save()
            OrderItem.objects.create(
                order=order,
                product=order.product,
                description=order.description,
                quantity=order.quantity or 1,
                weight_grams=order.weight_grams or 0.0,
                print_time_hours=order.print_time_hours or 0.0,
                print_time_minutes=order.print_time_minutes or 0,
                extra_costs=order.extra_costs or 0.00,
                unit_cost=order.unit_cost or 0.00,
                total_cost=order.total_cost or 0.00,
                unit_price=order.unit_price or 0.00,
                price=order.price or 0.00,
                status=order.status or 'Presupuestado',
                notes=order.notes or ''
            )
            return redirect('crm_dashboard')
    else:
        form = SmartOrderForm()
    
    products_qs = Product.objects.filter(is_active=True).prefetch_related('categories')
    products_with_id = []
    for p in products_qs:
        products_with_id.append({
            'id': p.id,
            'title': p.title,
            'price': float(p.price),
            'sale_price': float(p.sale_price) if p.sale_price else None,
            'is_on_sale': p.is_on_sale,
            'weight_grams': p.weight_grams or 0.0,
            'print_time_hours': p.print_time_hours or 0.0,
            'print_time_minutes': p.print_time_minutes or 0,
            'extra_costs': float(p.extra_costs or 0.0),
            'image_url': p.main_image.url if p.main_image else None,
            'category_name': p.category_names or 'Catálogo'
        })
    products = [p['title'] for p in products_with_id]
    
    return render(request, 'order_form.html', {
        'form': form, 
        'products': products, 
        'products_with_id': products_with_id,
        'products_json': json.dumps(products_with_id, default=str),
        'payment_methods': [c[0] for c in Order.PAYMENT_METHOD_CHOICES],
        'correos_services': CORREOS_SERVICES,
        'customers': Customer.objects.all().order_by('-updated_at')[:50],
    })

# =====================================================================
# VISTAS DEL CARRITO DE COMPRAS
# =====================================================================
import urllib.parse

def _get_or_create_cart(request):
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart

def cart_view(request):
    """Muestra el carrito y genera el enlace a WhatsApp con el pedido completo."""
    cart = _get_or_create_cart(request)
    items = cart.items.all().order_by('id')
    
    # Construir mensaje de WhatsApp
    if items.exists():
        message_lines = ["Hola ProPrint3d, quiero realizar el siguiente pedido:"]
        for item in items:
            absolute_url = request.build_absolute_uri(reverse('product_detail', args=[item.product.slug]))
            message_lines.append(f"- {item.quantity}x {item.product.title} ({item.unit_price}€/u) -> {absolute_url}")
        
        message_lines.append(f"\nTotal: {cart.total_price}€")
        wa_message = "\n".join(message_lines)
        wa_url = f"https://wa.me/34660904515?text={urllib.parse.quote(wa_message)}"
    else:
        wa_url = "#"
        
    context = {
        'cart': cart,
        'items': items,
        'wa_url': wa_url,
    }
    return render(request, 'cart.html', context)

def add_to_cart_view(request, product_id):
    """Añade un producto al carrito."""
    if request.method == 'POST':
        cart = _get_or_create_cart(request)
        product = get_object_or_404(Product, id=product_id)
        
        # Verificar si ya está en el carrito
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            cart_item.quantity += 1
            cart_item.save()
            
        return redirect(request.META.get('HTTP_REFERER', 'catalog'))
    return redirect('catalog')

def remove_from_cart_view(request, item_id):
    """Elimina un producto del carrito."""
    if request.method == 'POST':
        cart = _get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
    return redirect('cart')

def update_cart_view(request, item_id):
    """Actualiza la cantidad de un producto."""
    if request.method == 'POST':
        cart = _get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        action = request.POST.get('action')
        
        if action == 'increase':
            item.quantity += 1
            item.save()
        elif action == 'decrease':
            if item.quantity > 1:
                item.quantity -= 1
                item.save()
            else:
                item.delete()
    return redirect('cart')

# =====================================================================
# VISTA: download_product_model_file
# Propósito: Descarga segura de archivos 3D (.stl, .3mf) para administradores.
# =====================================================================
@staff_member_required
def download_product_model_file(request, slug):
    """
    Permite descargar el archivo STL/3MF adjunto a un producto.
    Acceso restringido exclusivamente a administradores y staff.
    """
    from django.http import FileResponse, Http404
    product = get_object_or_404(Product, slug=slug)
    if not product.model_file:
        raise Http404("Este producto no dispone de archivo 3D adjunto.")
    
    return FileResponse(
        product.model_file.open('rb'),
        as_attachment=True,
        filename=product.model_file_name
    )


# =====================================================================
# VISTAS: Logística Correos & Clientes Frecuentes
# =====================================================================

@staff_member_required
def order_thermal_label_view(request, order_id):
    """
    Renderiza la vista optimizada para imprimir etiqueta de envío en rollo continuo
    térmico de 58 mm.
    - Remitente oficial fijo con QR de proprint3d.shop
    - Destinatario sin teléfono ni email (privacidad y petición expresa)
    - Al final: datos de control interno (Pedido, peso estimado, servicio) separados
      por línea de corte discontinua para recortar antes de adherir.
    """
    order = get_object_or_404(Order, id=order_id)
    
    # Peso estimado: Suma dinámica de piezas + 100g tara (o peso manual si se configuró)
    weight_g = order.total_shipping_weight_grams
    if (not weight_g or weight_g <= 100) and order.shipping_package_weight and order.shipping_package_weight > 100:
        weight_g = order.shipping_package_weight
        
    service_names = dict(CORREOS_SERVICES)
    service_display = service_names.get(order.correos_service, order.correos_service or 'Carta Certificada')

    # Datos destinatario limpios
    dest_name = order.client_name
    dest_address = order.shipping_address or (order.customer.address if order.customer else '')
    dest_cp = order.shipping_postal_code or (order.customer.postal_code if order.customer else '')
    dest_city = order.shipping_city or (order.customer.city if order.customer else '')
    dest_province = order.shipping_province or (order.customer.province if order.customer else '')
    
    # Si no tiene desglose de dirección pero tiene texto en client_contact o shipping, proveer respaldo legible
    if not dest_address and order.shipping and order.shipping.lower() not in ['correos', 'envío', 'envio']:
        dest_address = order.shipping

    context = {
        'order': order,
        'dest_name': dest_name,
        'dest_address': dest_address,
        'dest_postal_code': dest_cp,
        'dest_city': dest_city,
        'dest_province': dest_province,
        'has_complete_address': bool(dest_address and dest_cp and dest_city),
        'correos_service_name': service_display,
        'estimated_weight_g': round(weight_g),
        'autoprint': request.GET.get('autoprint') == '1',
    }
    return render(request, 'shipping_thermal_label.html', context)


@staff_member_required
def api_customers_search(request):
    """
    API JSON para autocompletado y búsqueda de clientes habituales.
    Permite buscar por nombre, teléfono, email, ciudad o código postal.
    """
    q = request.GET.get('q', '').strip()
    customers_qs = Customer.objects.all()
    if q:
        customers_qs = customers_qs.filter(
            Q(name__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q) |
            Q(city__icontains=q) |
            Q(postal_code__icontains=q)
        )
    
    customers_qs = customers_qs.order_by('-updated_at')[:20]
    
    results = []
    for c in customers_qs:
        results.append({
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'email': c.email,
            'address': c.address,
            'postal_code': c.postal_code,
            'city': c.city,
            'province': c.province,
            'notes': c.notes,
            'full_address': c.full_address,
            'order_count': c.order_count,
            'total_spent': float(c.total_spent),
        })
        
    return JsonResponse({'success': True, 'customers': results})


@staff_member_required
def api_customer_save(request):
    """
    API JSON para crear o actualizar un cliente habitual.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)
        
    try:
        data = json.loads(request.body)
        cust_id = data.get('id')
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'success': False, 'error': 'El nombre del cliente es obligatorio.'}, status=400)
            
        if cust_id:
            customer = get_object_or_404(Customer, id=cust_id)
        else:
            customer = Customer()
            
        customer.name = name
        customer.phone = data.get('phone', '').strip()
        customer.email = data.get('email', '').strip()
        customer.address = data.get('address', '').strip()
        customer.postal_code = data.get('postal_code', '').strip()
        customer.city = data.get('city', '').strip()
        customer.province = data.get('province', '').strip()
        customer.notes = data.get('notes', '').strip()
        customer.save()
        
        return JsonResponse({
            'success': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'address': customer.address,
                'postal_code': customer.postal_code,
                'city': customer.city,
                'province': customer.province,
                'notes': customer.notes,
                'full_address': customer.full_address,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_calculate_shipping_rates(request):
    """
    API JSON para cotizar tarifas oficiales de Correos España 2026 en tiempo real.
    Acepta peso real de las piezas en gramos y aplica la tara de 100g de embalaje una sola vez.
    """
    weight_grams = float(request.GET.get('weight_grams') or request.POST.get('weight_grams') or 0.0)
    add_tare = request.GET.get('add_tare', '1') in ['1', 'true', True]
    packaging_margin = PACKAGING_TARE_DEFAULT_GRAMS if add_tare else 0

    length = request.GET.get('length') or request.POST.get('length')
    width = request.GET.get('width') or request.POST.get('width')
    height = request.GET.get('height') or request.POST.get('height')
    destination = request.GET.get('destination', 'peninsula')

    length_cm = float(length) if length else None
    width_cm = float(width) if width else None
    height_cm = float(height) if height else None

    analysis = calculate_all_correos_options(
        weight_grams=weight_grams,
        packaging_margin_grams=packaging_margin,
        length_cm=length_cm,
        width_cm=width_cm,
        height_cm=height_cm,
        destination=destination
    )
    
    return JsonResponse({'success': True, 'shipping_analysis': analysis})


@staff_member_required
def api_update_order_shipping(request, order_id):
    """
    API rápida para actualizar datos logísticos y número de seguimiento de un pedido
    directamente desde la tarjeta del CRM o desde la vista móvil.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)
        
    try:
        data = json.loads(request.body)
        order = get_object_or_404(Order, id=order_id)
        
        if 'correos_tracking_number' in data:
            order.correos_tracking_number = data['correos_tracking_number'].strip() if data['correos_tracking_number'] else ''
            
        if 'correos_service' in data and data['correos_service']:
            order.correos_service = data['correos_service'].strip()
            
        if 'shipping_cost_estimated' in data:
            try:
                order.shipping_cost_estimated = decimal.Decimal(str(data['shipping_cost_estimated']).replace(',', '.'))
            except Exception:
                pass

        if 'shipping_cost_paid_by' in data:
            order.shipping_cost_paid_by = data['shipping_cost_paid_by']
            
        if 'shipping_address' in data:
            order.shipping_address = data['shipping_address'].strip()
        if 'shipping_postal_code' in data:
            order.shipping_postal_code = data['shipping_postal_code'].strip()
        if 'shipping_city' in data:
            order.shipping_city = data['shipping_city'].strip()
        if 'shipping_province' in data:
            order.shipping_province = data['shipping_province'].strip()

        # Si se solicita avanzar estado a 'Enviado' automáticamente al registrar tracking
        if data.get('mark_as_shipped') and order.status != 'Enviado':
            order.status = 'Enviado'
            order.update_status_dates('Enviado')
            # También actualizar piezas a Enviado si procede
            order.items.exclude(status__in=['Enviado', 'Entregado', 'Cobrado']).update(status='Enviado')

        order.save()
        
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'correos_service': order.correos_service,
            'correos_tracking_number': order.correos_tracking_number,
            'correos_tracking_url': order.correos_tracking_url,
            'status': order.status,
            'formatted_shipping_address': order.formatted_shipping_address,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


SPANISH_PROVINCES = {
    '01': 'Álava / Araba', '02': 'Albacete', '03': 'Alicante / Alacant', '04': 'Almería',
    '05': 'Ávila', '06': 'Badajoz', '07': 'Illes Balears', '08': 'Barcelona', '09': 'Burgos',
    '10': 'Cáceres', '11': 'Cádiz', '12': 'Castellón / Castelló', '13': 'Ciudad Real',
    '14': 'Córdoba', '15': 'A Coruña', '16': 'Cuenca', '17': 'Girona', '18': 'Granada',
    '19': 'Guadalajara', '20': 'Gipuzkoa', '21': 'Huelva', '22': 'Huesca', '23': 'Jaén',
    '24': 'León', '25': 'Lleida', '26': 'La Rioja', '27': 'Lugo', '28': 'Madrid',
    '29': 'Málaga', '30': 'Murcia', '31': 'Navarra', '32': 'Ourense', '33': 'Asturias',
    '34': 'Palencia', '35': 'Las Palmas', '36': 'Pontevedra', '37': 'Salamanca',
    '38': 'Santa Cruz de Tenerife', '39': 'Cantabria', '40': 'Segovia', '41': 'Sevilla',
    '42': 'Soria', '43': 'Tarragona', '44': 'Teruel', '45': 'Toledo', '46': 'Valencia / València',
    '47': 'Valladolid', '48': 'Bizkaia', '49': 'Zamora', '50': 'Zaragoza', '51': 'Ceuta', '52': 'Melilla'
}

@staff_member_required
def api_postal_code_lookup(request, cp):
    """
    Autocompleta provincia y localidad a partir del código postal español.
    """
    cp_clean = str(cp).strip().zfill(5)
    prefix = cp_clean[:2]
    province = SPANISH_PROVINCES.get(prefix, '')
    city = ''

    # 1. Buscar primero en la base de datos local (clientes o pedidos anteriores)
    cust_match = Customer.objects.filter(postal_code=cp_clean).exclude(city='').first()
    if cust_match and cust_match.city:
        city = cust_match.city
    else:
        order_match = Order.objects.filter(shipping_postal_code=cp_clean).exclude(shipping_city='').first()
        if order_match and order_match.shipping_city:
            city = order_match.shipping_city

    # 2. Si no está en BD, consultar zippopotam.us
    if not city:
        import urllib.request
        import json
        try:
            url = f"https://api.zippopotam.us/es/{cp_clean}"
            req = urllib.request.Request(url, headers={'User-Agent': 'ProPrint3D/1.0'})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    places = data.get('places', [])
                    if places:
                        city = places[0].get('place name', '')
        except Exception:
            pass

    return JsonResponse({
        'success': True,
        'postal_code': cp_clean,
        'province': province,
        'city': city
    })


