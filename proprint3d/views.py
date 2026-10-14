import io
import decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.db.models import Q

from django.contrib.admin.views.decorators import staff_member_required

# Utilidades PDF
import io

from .models import Category, Product, Quote, QuoteItem, Order, OrderItem, ProductImage, Review, Cart, CartItem
from .forms import CalculatorForm, ProductFromCalcForm, ScraperForm, QuoteForm
from .utils.calculator import calculate_print_costs
from .utils.scraper import scrape_makerworld

# =====================================================================
# VISTA: catalog_view
# Propósito: Mostrar el catálogo público a los clientes.
# =====================================================================
def catalog_view(request):
    """Renderiza la vista principal pública con productos y filtros."""
    # Admins ven todos los productos (activos e inactivos), el público solo los activos
    if request.user.is_staff:
        products = Product.objects.all().order_by('-created_at')
    else:
        products = Product.objects.filter(is_active=True).order_by('-created_at')
    categories = Category.objects.all()
    
    # Manejo de búsqueda por texto y categoría
    search_query = request.GET.get('q', '')
    category_slug = request.GET.get('category', '')
    
    if search_query:
        # Busca en título o descripción usando Q objects (OR lógico)
        products = products.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
        
    if category_slug:
        if category_slug == 'ofertas':
            products = products.filter(is_on_sale=True)
        else:
            products = products.filter(category__slug=category_slug)
        
    context = {
        'products': products,
        'categories': categories,
        'search_query': search_query,
        'category_slug': category_slug,
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
def product_detail_view(request, slug):
    """Muestra detalles extendidos de una pieza del catálogo."""
    # Admins pueden ver productos ocultos (is_active=False)
    if request.user.is_staff:
        product = get_object_or_404(Product, slug=slug)
    else:
        product = get_object_or_404(Product, slug=slug, is_active=True)
        
    related_products = []
    if product.category:
        related_products = Product.objects.filter(
            category=product.category, 
            is_active=True
        ).exclude(id=product.id).order_by('?')[:5]
    
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
            new_category_name = form.cleaned_data.get('new_category')
            
            if new_category_name:
                cat, _ = Category.objects.get_or_create(name=new_category_name)
                product.category = cat
            
            product.save()
            
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
                new_category_name = product_form_post.cleaned_data.get('new_category')
                
                # Si escribió una nueva categoría, crearla y asignarla
                if new_category_name:
                    cat, _ = Category.objects.get_or_create(name=new_category_name)
                    product.category = cat
                
                product.save()
                
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

def generate_quote_pdf_view(request, quote_id):
    """
    Busca el presupuesto, genera un PDF en memoria usando una plantilla HTML
    y lo devuelve como archivo descargable.
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
    
    # Retornar como respuesta HTTP
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Presupuesto_{quote.id}_{quote.client_name}.pdf"'
    
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
            status=ord_obj.status or 'Presupuestado'
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

        card_groups = []
        for oid, data in orders_map.items():
            data['all_items_in_this_col'] = (len(data['items']) == data['total_items_in_order'])
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
        'payment_methods': [c[0] for c in Order.PAYMENT_METHOD_CHOICES],
        'status_choices': [c[0] for c in Order.STATUS_CHOICES]
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
            'client_name', 'order_date', 'deadline', 'status', 'quantity', 
            'weight_grams', 'print_time_hours', 'print_time_minutes', 'extra_costs',
            'unit_cost', 'total_cost', 'unit_price', 'price',
            'shipped_date', 'delivered_date', 'paid_date',
            'platform', 'shipping', 'notes',
            'deposit_amount', 'deposit_method', 'final_payment_method', 'payment_notes'
        ]
        widgets = {
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
        order_date = request.POST.get('order_date')
        deadline = request.POST.get('deadline') or None
        platform = request.POST.get('platform', '').strip()
        shipping = request.POST.get('shipping', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        parsed_pieces = []
        if pieces_json:
            try:
                parsed_pieces = json.loads(pieces_json)
            except Exception:
                parsed_pieces = []
                
        initial_status = request.POST.get('status', 'Presupuestado').strip() or 'Presupuestado'
        if initial_status not in dict(Order.STATUS_CHOICES):
            initial_status = 'Presupuestado'

        raw_dep = request.POST.get('deposit_amount', '').strip().replace(',', '.')
        try:
            deposit_val = decimal.Decimal(raw_dep) if raw_dep else decimal.Decimal('0.00')
        except Exception:
            deposit_val = decimal.Decimal('0.00')
        deposit_method_val = request.POST.get('deposit_method', '').strip()
        final_payment_method_val = request.POST.get('final_payment_method', '').strip()
        payment_notes_val = request.POST.get('payment_notes', '').strip()

        if client_name and order_date and parsed_pieces:
            order = Order.objects.create(
                client_name=client_name,
                order_date=order_date,
                deadline=deadline,
                platform=platform,
                shipping=shipping,
                notes=notes,
                status=initial_status,
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
                    status=initial_status
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
                status=order.status or 'Presupuestado'
            )
            return redirect('crm_dashboard')
    else:
        form = SmartOrderForm()
    
    products_qs = Product.objects.filter(is_active=True).select_related('category')
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
            'category_name': p.category.name if p.category else 'Catálogo'
        })
    products = [p['title'] for p in products_with_id]
    
    return render(request, 'order_form.html', {
        'form': form, 
        'products': products, 
        'products_with_id': products_with_id,
        'products_json': json.dumps(products_with_id, default=str),
        'payment_methods': [c[0] for c in Order.PAYMENT_METHOD_CHOICES],
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

