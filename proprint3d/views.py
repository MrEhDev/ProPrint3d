import io
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.db.models import Q

from django.contrib.admin.views.decorators import staff_member_required

# Utilidades PDF
import io

# Modelos, Formularios y Utilidades
from .models import Category, Product, Quote, QuoteItem, Order, ProductImage, Review
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
    
    absolute_url = request.build_absolute_uri()
    wa_message = f"Hola ProPrint3d, estoy interesado en la pieza: {product.title}\n\nEnlace: {absolute_url}"
    import urllib.parse
    wa_url = f"https://wa.me/34600000000?text={urllib.parse.quote(wa_message)}"
    
    context = {
        'product': product,
        'wa_url': wa_url
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
                product_form = ProductFromCalcForm(initial={
                    'title': scraped_data['title'],
                    'description': scraped_data['description'],
                    'makerworld_url': url
                })
                
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
from django.db.models import Sum, F

@staff_member_required
def crm_dashboard_view(request):
    """
    Muestra la lista de pedidos y calcula estadísticas generales.
    """
    month_filter = request.GET.get('month')
    year_filter = request.GET.get('year')
    orders = Order.objects.all().order_by('-order_date')
    
    if month_filter:
        try:
            orders = orders.filter(order_date__month=int(month_filter))
        except ValueError:
            pass
            
    if year_filter:
        try:
            orders = orders.filter(order_date__year=int(year_filter))
        except ValueError:
            pass
            
    # Kanban: pedidos no cobrados
    unpaid_orders_qs = orders.exclude(status='Cobrado').exclude(status='Cancelado')
    kanban_columns = {
        'Pendiente': unpaid_orders_qs.filter(status='Pendiente'),
        'Realizado': unpaid_orders_qs.filter(status='Realizado'),
        'Pdt de envío': unpaid_orders_qs.filter(status='Pdt de envío'),
        'Pdt. entrega': unpaid_orders_qs.filter(status='Pdt. entrega'),
        'Enviado': unpaid_orders_qs.filter(status='Enviado'),
        'Entregado': unpaid_orders_qs.filter(status='Entregado'),
    }
    
    # Cálculos globales (excluir cancelados)
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
        'current_month': month_filter,
        'current_year': year_filter,
        'total_sales': total_sales,
        'total_costs': total_costs,
        'total_profit': total_profit,
        'avg_profit': avg_profit
    }
    
    return render(request, 'crm_dashboard.html', context)
from django.http import JsonResponse
import json

@staff_member_required
def update_order_status_api(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            order = Order.objects.get(id=order_id)
            if new_status in [s[0] for s in Order.STATUS_CHOICES]:
                order.status = new_status
                order.save()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Estado inválido'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

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
        widget=forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white border-gray-300 dark:border-gray-700 focus:border-primary', 'list': 'products-datalist'})
    )

    class Meta:
        model = Order
        fields = ['client_name', 'order_date', 'status', 'quantity', 'price', 'platform', 'shipping']
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].required = False
        
        # Add Tailwind classes dynamically
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-input w-full rounded-md bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white border-gray-300 dark:border-gray-700 focus:border-primary'})

@staff_member_required
def order_create_view(request):
    if request.method == 'POST':
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
                
            order.save()
            return redirect('crm_dashboard')
    else:
        form = SmartOrderForm()
    
    products = Product.objects.filter(is_active=True).values_list('title', flat=True)
    products_with_id = Product.objects.filter(is_active=True).values(
        'id', 'title', 'price', 'weight_grams', 'print_time_hours', 'print_time_minutes', 'extra_costs'
    )
    return render(request, 'order_form.html', {'form': form, 'products': products, 'products_with_id': products_with_id})
