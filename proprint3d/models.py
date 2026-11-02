from django.db import models
from django.utils.text import slugify
from django.core.files.base import ContentFile
import io
from PIL import Image

def compress_image_field(image_field, max_width=1200, quality=80):
    """
    Comprime y redimensiona una imagen usando Pillow.
    Devuelve True si se ha modificado, False si no (ej. si no hay imagen).
    """
    if not image_field:
        return False
        
    try:
        # Abrir imagen original
        img = Image.open(image_field)
        
        # Convertir a RGB si es PNG con transparencia para guardar como JPEG
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # Redimensionar si es muy grande
        if img.width > max_width:
            output_size = (max_width, int((max_width/img.width) * img.height))
            img = img.resize(output_size, Image.Resampling.LANCZOS)
            
        # Guardar en memoria
        output_io = io.BytesIO()
        img.save(output_io, format='JPEG', quality=quality, optimize=True)
        
        # Cambiar el archivo en el campo (con extensión .jpg)
        file_name = image_field.name.split('.')[0] + '.jpg'
        image_field.save(file_name, ContentFile(output_io.getvalue()), save=False)
        return True
    except Exception as e:
        # En caso de error, no modificamos la imagen original
        print("Error comprimiendo imagen:", e)
        return False

# =====================================================================
# MODELO: Category
# Propósito: Agrupar los productos (piezas 3D) en distintas familias
# o categorías lógicas (ej: "Soportes", "Figuras", "Mecánica").
# Razón de la estructura: Permite un filtrado sencillo en el front-end.
# =====================================================================
class Category(models.Model):
    # 'name': Nombre visible de la categoría
    name = models.CharField(max_length=100, unique=True)
    # 'slug': Versión URL-friendly del nombre para usar en las rutas
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    # 'description': Texto opcional para describir el tipo de piezas
    description = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para auto-generar el slug
        a partir del nombre si no se ha proporcionado uno.
        """
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# =====================================================================
# MODELO: Product
# Propósito: Representa una pieza de impresión 3D disponible en el catálogo.
# Razón de la estructura: Almacena todos los metadatos necesarios tanto
# para su visualización (título, imagen, precio) como para el cálculo 
# de presupuestos (peso, tiempo de impresión).
# =====================================================================
class Product(models.Model):
    categories = models.ManyToManyField(Category, blank=True, related_name='products')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    main_image = models.ImageField(upload_to='products/', blank=True, null=True)
    dimensions = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: 10x10x15 cm")
    
    # Precios y métricas
    price = models.DecimalField(max_digits=10, decimal_places=2) # Precio de venta al público
    is_on_sale = models.BooleanField(default=False, help_text="¿Está de oferta?")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio rebajado")
    
    weight_grams = models.FloatField(null=True, blank=True, help_text="Peso estimado en gramos (incluyendo soportes)")
    print_time_hours = models.FloatField(null=True, blank=True, help_text="Tiempo de impresión en horas (ej. 2)")
    print_time_minutes = models.IntegerField(null=True, blank=True, help_text="Tiempo de impresión extra en minutos (ej. 30)")
    extra_costs = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Otros costes (Pintura, cajas, etc. en €)")
    
    # Metadatos externos
    makerworld_url = models.URLField(blank=True, null=True, help_text="Enlace original si proviene de MakerWorld")
    
    # Archivo 3D privado (STL, 3MF, STEP, etc) accesible solo por administradores
    model_file = models.FileField(
        upload_to='models_3d/', 
        blank=True, 
        null=True, 
        help_text="Archivo 3D (.stl, .3mf, .step, .zip) accesible solo por administradores"
    )

    # Estados y auditoría
    is_active = models.BooleanField(default=True, help_text="¿Visible en el catálogo?")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def model_file_name(self):
        if self.model_file:
            import os
            return os.path.basename(self.model_file.name)
        return None


    @property
    def model_file_extension(self):
        if self.model_file:
            import os
            _, ext = os.path.splitext(self.model_file.name)
            return ext.lower().replace('.', '')
        return ''

    @property
    def category(self):
        """Devuelve la primera categoría asignada para compatibilidad regresiva."""
        return self.categories.first()

    @property
    def category_names(self):
        """Devuelve los nombres de las categorías separados por comas."""
        return ", ".join(c.name for c in self.categories.all())

    def save(self, *args, **kwargs):
        """
        Sobrescribe save para asegurar que siempre haya un slug único 
        y comprimir la imagen principal si ha cambiado.
        """
        if not self.slug:
            original_slug = slugify(self.title)
            queryset = Product.objects.all()
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            
            slug = original_slug
            counter = 1
            while queryset.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
            self.slug = slug
            
        # Comprimir imagen solo si es nueva o ha cambiado
        do_compress = False
        if self.main_image:
            if not self.pk:
                do_compress = True
            else:
                try:
                    old = Product.objects.get(pk=self.pk)
                    if old.main_image != self.main_image:
                        do_compress = True
                except Product.DoesNotExist:
                    do_compress = True
                    
        if do_compress:
            compress_image_field(self.main_image)
            
        super().save(*args, **kwargs)

    def calculate_production_cost(self):
        """
        Calcula el coste de producción igual que la calculadora JS:
        Filamento + Energía + Desgaste + 15% Margen + Extras
        """
        w = float(self.weight_grams or 0)
        h = float(self.print_time_hours or 0)
        m = float(self.print_time_minutes or 0)
        extra = float(self.extra_costs or 0)
        
        total_hours = h + (m / 60)
        
        if w > 0 and total_hours > 0:
            cost_filament = 0.02 * w
            cost_energy = 0.15 * 0.12 * total_hours
            cost_wear = 0.30 * total_hours
            
            cost_subtotal = cost_filament + cost_energy + cost_wear
            error_margin = cost_subtotal * 0.15
            
            return round(cost_subtotal + error_margin + extra, 2)
        return 0.0

    def __str__(self):
        return self.title

# =====================================================================
# MODELO: ProductImage
# Propósito: Almacena múltiples imágenes para crear galerías/carruseles.
# =====================================================================
class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/gallery/')
    is_cover = models.BooleanField(default=False, help_text="¿Es la imagen principal?")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """
        Si esta imagen es la portada, asegura que las demás del producto no lo sean.
        Además comprime la imagen al subirla.
        """
        if self.is_cover:
            ProductImage.objects.filter(product=self.product).update(is_cover=False)
            
        # Comprimir imagen solo si es nueva o ha cambiado
        do_compress = False
        if self.image:
            if not self.pk:
                do_compress = True
            else:
                try:
                    old = ProductImage.objects.get(pk=self.pk)
                    if old.image != self.image:
                        do_compress = True
                except ProductImage.DoesNotExist:
                    do_compress = True
                    
        if do_compress:
            compress_image_field(self.image)
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen para {self.product.title}"

# =====================================================================
# MODELO: Quote
# Propósito: Cabecera para almacenar presupuestos generados a clientes.
# Razón de la estructura: Permite guardar el estado de una negociación,
# asociarlo a un cliente y calcular los totales desde las líneas hijas.
# =====================================================================
class Quote(models.Model):
    STATUS_CHOICES = (
        ('Draft', 'Borrador'),
        ('Sent', 'Enviado'),
        ('Accepted', 'Aceptado'),
    )
    client_name = models.CharField(max_length=150)
    client_contact = models.CharField(max_length=150, help_text="Email o Teléfono")
    created_at = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    include_tax = models.BooleanField(default=False)
    tax_name = models.CharField(max_length=50, default="IVA incl.")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=21.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    notes = models.TextField(blank=True, null=True)

    def update_total(self):
        """
        Método para recalcular el precio total del presupuesto sumando
        los costes calculados de cada QuoteItem asociado.
        Se llama cada vez que se modifica una línea.
        """
        # Sumamos 'calculated_cost' de todos los items
        total_items = sum((item.calculated_cost or 0) for item in self.items.all())
        self.subtotal = total_items
        
        if self.include_tax:
            self.tax_amount = (self.subtotal * self.tax_percentage) / 100
            self.total_price = self.subtotal + self.tax_amount
        else:
            self.tax_amount = 0
            self.total_price = self.subtotal
            
        self.save()

    def __str__(self):
        return f"Quote #{self.id} - {self.client_name}"

# =====================================================================
# MODELO: QuoteItem
# Propósito: Línea de detalle de un presupuesto (piezas solicitadas).
# Razón de la estructura: Un ítem puede referenciar a un 'Product'
# del catálogo o ser una pieza 'custom' (sin FK). Por eso 'product'
# puede ser nulo, usando 'custom_title' en su lugar.
# =====================================================================
class QuoteItem(models.Model):
    quote = models.ForeignKey(Quote, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    custom_title = models.CharField(max_length=200, blank=True, null=True, help_text="Usar si no es un producto del catálogo")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    calculated_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        """
        Antes de guardar, calcula el coste total de esta línea
        (precio unitario * cantidad).
        """
        # Lógica matemática: multiplicar unit_price x quantity
        if self.unit_price is not None and self.quantity is not None:
            self.calculated_cost = self.unit_price * self.quantity
        else:
            self.calculated_cost = 0
            
        # Si se seleccionó un producto y no se dio título custom, usar el del producto
        if self.product and not self.custom_title:
            self.custom_title = self.product.title
            
        super().save(*args, **kwargs)
        # Actualizamos el total de la cabecera del presupuesto
        self.quote.update_total()

    def __str__(self):
        return f"{self.quantity}x {self.custom_title}"

# =====================================================================
# MODELO: Order
# Propósito: Mini-CRM para control de pedidos.
# Razón de la estructura: Separado de los presupuestos para enfocarse en 
# ventas cerradas y rentabilidad por plataforma y envío.
# =====================================================================
class Order(models.Model):
    STATUS_CHOICES = [
        ('Presupuestado', 'Presupuestado'),
        ('En proceso', 'En proceso'),
        ('Realizado', 'Realizado'),
        ('Enviado', 'Enviado'),
        ('Entregado', 'Entregado'),
        ('Cobrado', 'Cobrado'),
        ('Cancelado', 'Cancelado')
    ]
    
    PLATFORM_CHOICES = [
        ('Wallapop', 'Wallapop'),
        ('Wallapop Elyest', 'Wallapop Elyest'),
        ('Vinted', 'Vinted'),
        ('Web', 'Web'),
        ('Directo', 'Directo'),
        ('Otro', 'Otro')
    ]
    
    SHIPPING_CHOICES = [
        ('Inpost', 'Inpost'),
        ('Correos', 'Correos'),
        ('GLS', 'GLS'),
        ('En mano', 'En mano'),
        ('Otro', 'Otro')
    ]

    PAYMENT_METHOD_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Bizum', 'Bizum'),
        ('Vinted', 'Vinted'),
        ('Wallapop', 'Wallapop'),
        ('Wallapop Elyest', 'Wallapop Elyest'),
        ('Transferencia', 'Transferencia bancaria'),
        ('Web', 'Web / Tarjeta'),
        ('Otro', 'Otro')
    ]

    order_date = models.DateField(help_text="Fecha de Pedido")
    quantity = models.IntegerField(default=1, help_text="Cantidad")
    
    # Puede estar linkado a un producto, pero permitimos nombre libre si es un custom
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=250, blank=True, null=True, help_text="Descripción del Pedido (Ej. Fiat Panda Rally)")
    
    client_name = models.CharField(max_length=150, help_text="Nombre de la Persona")
    client_contact = models.CharField(max_length=150, blank=True, null=True, default='', help_text="Email, teléfono o usuario de contacto")
    
    # Métricas de fabricación y costes por unidad
    weight_grams = models.FloatField(null=True, blank=True, help_text="Peso estimado en gramos por unidad")
    print_time_hours = models.FloatField(null=True, blank=True, help_text="Horas de impresión por unidad")
    print_time_minutes = models.IntegerField(null=True, blank=True, help_text="Minutos extra de impresión por unidad")
    extra_costs = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00, help_text="Otros costes por unidad (€)")
    
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00, help_text="Coste Unitario Producción (€)")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Coste Total Producción (€)")
    
    # Precios cobrados
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio Unitario Cobrado (€)")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio Final Cobrado (€)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Presupuestado')
    deadline = models.DateField(null=True, blank=True, help_text="Fecha límite")
    
    # Fechas de seguimiento de estado
    shipped_date = models.DateField(null=True, blank=True, help_text="Fecha de Envío")
    delivered_date = models.DateField(null=True, blank=True, help_text="Fecha de Entrega")
    paid_date = models.DateField(null=True, blank=True, help_text="Fecha de Cobro")
    
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, blank=True, null=True, default='', help_text="Plataforma de venta")
    shipping = models.CharField(max_length=50, choices=SHIPPING_CHOICES, blank=True, null=True, default='', help_text="Método de envío")
    
    notes = models.TextField(blank=True, null=True, help_text="Notas adicionales")
    has_vat = models.BooleanField(default=False, help_text="¿Incluye IVA (21%) en el precio total?")
    has_irpf = models.BooleanField(default=False, help_text="¿Descontar IRPF (21%) de la ganancia?")

    # Gestión de Pagos y Paga y Señal
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Paga y señal / Adelanto cobrado (€)")
    deposit_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True, default='', help_text="Método del adelanto")
    final_payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True, default='', help_text="Método de cobro restante/final")
    payment_notes = models.CharField(max_length=255, blank=True, null=True, default='', help_text="Detalles o notas sobre los pagos")

    created_at = models.DateTimeField(auto_now_add=True)

    def update_status_dates(self, new_status=None):
        """Actualiza automáticamente las fechas de estado si no han sido fijadas."""
        import datetime
        current = new_status or self.status
        today = datetime.date.today()
        if current == 'Enviado' and not self.shipped_date:
            self.shipped_date = today
        elif current == 'Entregado':
            if not self.delivered_date:
                self.delivered_date = today
            if not self.shipped_date:
                self.shipped_date = today
        elif current == 'Cobrado':
            if not self.paid_date:
                self.paid_date = today
            if not self.delivered_date:
                self.delivered_date = today
            if not self.shipped_date:
                self.shipped_date = today

    def calculate_unit_cost(self):
        """Calcula el coste unitario de producción según peso, tiempo y extras."""
        w = float(self.weight_grams or 0)
        h = float(self.print_time_hours or 0)
        m = float(self.print_time_minutes or 0)
        extra = float(self.extra_costs or 0)
        
        total_hours = h + (m / 60)
        if w > 0 and total_hours > 0:
            cost_filament = 0.02 * w
            cost_energy = 0.15 * 0.12 * total_hours
            cost_wear = 0.30 * total_hours
            cost_subtotal = cost_filament + cost_energy + cost_wear
            error_margin = cost_subtotal * 0.15
            return round(cost_subtotal + error_margin + extra, 2)
        elif self.product:
            return float(self.product.calculate_production_cost())
        return 0.0

    def save(self, *args, **kwargs):
        import decimal
        qty = decimal.Decimal(str(self.quantity or 1))
        
        if self.unit_price is not None:
            self.unit_price = decimal.Decimal(str(self.unit_price))
        if self.price is not None:
            self.price = decimal.Decimal(str(self.price))
        if self.unit_cost is not None:
            self.unit_cost = decimal.Decimal(str(self.unit_cost))
        if self.total_cost is not None:
            self.total_cost = decimal.Decimal(str(self.total_cost))
        if self.extra_costs is not None:
            self.extra_costs = decimal.Decimal(str(self.extra_costs))
        
        # Auto-completar descripción si hay producto y no hay descripción manual
        if self.product and not self.description:
            self.description = self.product.title
            
        # Si hay producto y los datos de fabricación están vacíos, rellenarlos desde el producto
        if self.product:
            if self.weight_grams is None:
                self.weight_grams = self.product.weight_grams
            if self.print_time_hours is None:
                self.print_time_hours = self.product.print_time_hours
            if self.print_time_minutes is None:
                self.print_time_minutes = self.product.print_time_minutes
            if self.extra_costs is None or self.extra_costs == 0:
                self.extra_costs = self.product.extra_costs or decimal.Decimal('0.00')

        # Auto-asignar fechas según estado
        self.update_status_dates()

        # Calcular coste unitario
        calc_u_cost = self.calculate_unit_cost()
        if calc_u_cost > 0:
            self.unit_cost = decimal.Decimal(str(calc_u_cost))
        elif self.unit_cost is None:
            self.unit_cost = decimal.Decimal('0.00')
            
        # Calcular coste total si está vacío o es 0
        if (self.total_cost is None or self.total_cost == 0) and self.unit_cost:
            self.total_cost = self.unit_cost * qty

        # Calcular precio unitario y total
        if self.unit_price is not None and self.unit_price > 0:
            if self.price is None or self.price == 0:
                self.price = self.unit_price * qty
        elif self.price is not None and self.price > 0:
            if self.unit_price is None or self.unit_price == 0:
                self.unit_price = round(self.price / qty, 2)
        elif self.product:
            product_p = self.product.sale_price if (self.product.is_on_sale and self.product.sale_price) else self.product.price
            self.unit_price = product_p
            self.price = product_p * qty
            
        super().save(*args, **kwargs)

    @property
    def hourly_rate_info(self):
        """Ratio de rentabilidad horaria de la pieza individual (€/h)."""
        h = float(self.print_time_hours or 0) + (float(self.print_time_minutes or 0) / 60.0)
        total_item_hours = h * (self.quantity or 1)
        if total_item_hours <= 0:
            return None
        try:
            p = float(self.profit)
        except Exception:
            return None
        rate = round(p / total_item_hours, 2)
        rate_str = f"{rate:.2f} €/h"
        if rate >= 6.0:
            badge_css = 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
            icon = '⚡'
        elif rate >= 3.0:
            badge_css = 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30'
            icon = '⚡'
        else:
            badge_css = 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30 font-bold'
            icon = '⚠️'
        return {
            'rate': rate,
            'rate_str': rate_str,
            'icon': icon,
            'badge_css': badge_css
        }

    @property
    def profit(self):
        """Calcula la ganancia real descontando el coste de producción, considerando IVA e IRPF si aplican."""
        import decimal
        if self.price is not None and self.total_cost is not None:
            p = decimal.Decimal(str(self.price))
            c = decimal.Decimal(str(self.total_cost))
            
            # Si incluye IVA, la base imponible sobre la que se calcula la ganancia es p / 1.21
            if self.has_vat:
                base_p = p / decimal.Decimal('1.21')
            else:
                base_p = p
                
            base_profit = base_p - c
            
            # Si descuenta IRPF, descuenta un 21% de la ganancia total
            if self.has_irpf:
                return round(base_profit * decimal.Decimal('0.79'), 2) if base_profit > 0 else round(base_profit, 2)
            return round(base_profit, 2)
        return decimal.Decimal('0.00')

    @property
    def are_all_items_realizado(self):
        """Devuelve True si todas las piezas del pedido están en estado 'Realizado'."""
        items = list(self.items.all())
        if not items:
            return self.status == 'Realizado'
        return all(i.status == 'Realizado' for i in items)

    @property
    def is_all_completed(self):
        """Devuelve True si todas las piezas están realizadas o si el pedido ya está en fase de entrega/cobro."""
        if self.status in ['Realizado', 'Enviado', 'Entregado', 'Cobrado']:
            return True
        items = list(self.items.all())
        if not items:
            return False
        return all(i.status in ['Realizado', 'Enviado', 'Entregado', 'Cobrado'] for i in items)

    @property
    def whatsapp_url(self):
        """
        Si el contacto del cliente contiene un número móvil (ej. 6XXXXXXXX, 7XXXXXXXX, +34..., 0034...),
        devuelve la URL de WhatsApp (https://wa.me/34XXXXXXXXX). Si no es un teléfono, devuelve None.
        """
        import re
        if not self.client_contact:
            return None
        raw = str(self.client_contact).strip()
        if '@' in raw:
            return None
        digits = re.sub(r'\D', '', raw)
        if not digits:
            return None
        # Teléfono móvil español de 9 dígitos empezando por 6 o 7
        if len(digits) == 9 and digits[0] in ('6', '7'):
            return f"https://wa.me/34{digits}"
        # Si ya incluye prefijo 34 (11 dígitos) y empieza por 6 o 7
        elif len(digits) == 11 and digits.startswith('34') and digits[2] in ('6', '7'):
            return f"https://wa.me/{digits}"
        # Si incluye prefijo 0034 (13 dígitos)
        elif len(digits) == 13 and digits.startswith('0034') and digits[4] in ('6', '7'):
            return f"https://wa.me/{digits[2:]}"
        # Otros teléfonos internacionales de al menos 9 dígitos
        elif len(digits) >= 9:
            if raw.startswith('+'):
                return f"https://wa.me/{digits}"
            if len(digits) == 9:
                return f"https://wa.me/34{digits}"
            return f"https://wa.me/{digits}"
        return None

    @property
    def deadline_info(self):
        """
        Calcula el estado y código de color de la fecha límite según el tiempo restante
        y la duración acumulada de impresión.
        Cuando el pedido pasa a 'Enviado', 'Entregado' o 'Cobrado', ya no se muestra la fecha límite.
        """
        import datetime
        if not self.deadline:
            return None
        
        # Si el pedido ya ha sido enviado, entregado o cobrado, ya no se muestra
        if self.status in ['Enviado', 'Entregado', 'Cobrado']:
            return None
        
        today = datetime.date.today()
        days_left = (self.deadline - today).days

        # Duración acumulada de impresión en horas
        items = list(self.items.all())
        if items:
            total_mins = sum(((i.print_time_hours or 0.0) * 60 + (i.print_time_minutes or 0)) * (i.quantity or 1) for i in items)
        else:
            total_mins = ((self.print_time_hours or 0.0) * 60 + (self.print_time_minutes or 0)) * (self.quantity or 1)
        print_hours = total_mins / 60.0

        h_int = int(total_mins // 60)
        m_int = int(total_mins % 60)
        duration_str = f"{h_int}h {m_int}m" if total_mins > 0 else "0h"

        # Lógica de color según tiempo restante y horas de impresión requeridas
        # 1. Vencido: fecha límite ya superada
        if days_left < 0:
            level = 'overdue'
            color = 'red'
            icon = '🚨'
            days_abs = abs(days_left)
            text = f"Vencido hace {days_abs}d" if days_abs > 1 else "Vencido ayer"
            css = "bg-red-500/20 text-red-700 dark:text-red-400 border-red-500/40 ring-1 ring-red-500/30 animate-pulse font-bold"
            tooltip = f"¡Límite superado! Vencido hace {days_abs} días. Impresión estimada: {duration_str}"
        # 2. Crítico / Urgente: vence hoy, o queda <= 1 día, o las horas de impresión superan el tiempo disponible (asumiendo ~12h productivas/día)
        elif days_left == 0 or (print_hours > 0 and (days_left * 12) < print_hours) or days_left <= 1:
            level = 'critical'
            color = 'rose'
            icon = '🔥'
            if days_left == 0:
                text = "¡Vence hoy!"
            elif days_left == 1:
                text = "Queda 1 día"
            else:
                text = f"Quedan {days_left}d (Impr: {duration_str})"
            css = "bg-rose-500/20 text-rose-700 dark:text-rose-400 border-rose-500/40 font-bold"
            tooltip = f"¡Urgente! Margen crítico frente a {duration_str} de impresión necesaria."
        # 3. Advertencia: quedan 2 o 3 días, o el margen de impresión es moderadamente ajustado
        elif days_left <= 3 or (print_hours > 0 and (days_left * 16) < (print_hours * 1.8)):
            level = 'warning'
            color = 'amber'
            icon = '⏳'
            text = f"Quedan {days_left} días"
            css = "bg-amber-500/20 text-amber-800 dark:text-amber-300 border-amber-500/40 font-semibold"
            tooltip = f"Atención: Quedan {days_left} días para la entrega. Impresión estimada: {duration_str}"
        # 4. En plazo holgado
        else:
            level = 'safe'
            color = 'emerald'
            icon = '📅'
            text = f"Quedan {days_left} días"
            css = "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border-emerald-500/30 font-medium"
            tooltip = f"En plazo: Quedan {days_left} días. Impresión estimada: {duration_str}"

        return {
            'level': level,
            'color': color,
            'icon': icon,
            'text': text,
            'css': css,
            'tooltip': tooltip,
            'days_left': days_left,
            'duration_str': duration_str,
            'formatted_date': self.deadline.strftime('%d/%m/%Y'),
            'short_date': self.deadline.strftime('%d/%m'),
            'is_urgent': level in ['overdue', 'critical', 'warning'],
        }

    @property
    def remaining_amount(self):
        """Calcula el importe que queda por cobrar tras la paga y señal."""
        import decimal
        p = self.price or decimal.Decimal('0.00')
        d = self.deposit_amount or decimal.Decimal('0.00')
        rem = p - d
        return max(decimal.Decimal('0.00'), rem)

    @property
    def payment_summary_text(self):
        """Genera un texto resumen amigable de cómo se ha cobrado el pedido."""
        import decimal
        p = self.price or decimal.Decimal('0.00')
        d = self.deposit_amount or decimal.Decimal('0.00')
        dep_method = self.deposit_method or 'Adelanto'
        final_method = self.final_payment_method or 'Cobro'

        if d > 0 and self.status == 'Cobrado':
            rem = max(decimal.Decimal('0.00'), p - d)
            if rem > 0:
                return f"€{d:.2f} ({dep_method}) + €{rem:.2f} ({final_method})"
            else:
                return f"€{d:.2f} ({dep_method})"
        elif d > 0:
            rem = max(decimal.Decimal('0.00'), p - d)
            return f"Señal: €{d:.2f} ({dep_method}) · Pendiente: €{rem:.2f}"
        elif self.status == 'Cobrado' and self.final_payment_method:
            return f"€{p:.2f} ({final_method})"
        elif self.status == 'Cobrado':
            return f"€{p:.2f} (Cobrado)"
        return "Pendiente de cobro"

    @property
    def total_weight_calc(self):
        """Peso total acumulado de las piezas del pedido."""
        items = list(self.items.all())
        if items:
            return sum((i.weight_grams or 0.0) * (i.quantity or 1) for i in items)
        return (self.weight_grams or 0.0) * (self.quantity or 1)

    @property
    def total_print_time_hours(self):
        """Horas totales de impresión acumuladas (en decimal)."""
        items = list(self.items.all())
        if items:
            mins = sum(((i.print_time_hours or 0.0) * 60 + (i.print_time_minutes or 0)) * (i.quantity or 1) for i in items)
        else:
            mins = ((self.print_time_hours or 0.0) * 60 + (self.print_time_minutes or 0)) * (self.quantity or 1)
        return round(mins / 60.0, 2)

    @property
    def hourly_rate_info(self):
        """
        Ratio de Eficiencia Horaria: Beneficio neto por hora de máquina ocupada (€/h).
        Clasificación de rendimiento:
          - >= 6.00 €/h: Excelente rentabilidad (verde)
          - 3.00 - 5.99 €/h: Rentabilidad estándar / aceptable (ámbar)
          - < 3.00 €/h: Alerta de baja rentabilidad horaria (rojo)
        """
        h = self.total_print_time_hours
        if h <= 0:
            return None
        
        try:
            p = float(self.profit)
        except Exception:
            return None

        rate = p / h
        rate_rounded = round(rate, 2)
        rate_str = f"{rate_rounded:.2f} €/h"

        if rate >= 6.0:
            level = 'excellent'
            color = 'emerald'
            icon = '⚡'
            badge_css = 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border-emerald-500/30'
            tooltip = f"Eficiencia horaria excelente: genera {rate_str} de beneficio neto por hora de máquina ocupada ({self.total_print_time_str} en total)."
        elif rate >= 3.0:
            level = 'normal'
            color = 'amber'
            icon = '⚡'
            badge_css = 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/30'
            tooltip = f"Eficiencia horaria estándar: genera {rate_str} por hora de máquina ocupada ({self.total_print_time_str} en total)."
        else:
            level = 'low'
            color = 'red'
            icon = '⚠️'
            badge_css = 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30 font-bold'
            tooltip = f"¡Alerta de baja rentabilidad horaria! Solo genera {rate_str} ocupando la máquina durante {self.total_print_time_str}."

        return {
            'rate': rate_rounded,
            'rate_str': rate_str,
            'text': rate_str,
            'level': level,
            'color': color,
            'icon': icon,
            'badge_css': badge_css,
            'tooltip': tooltip,
            'print_hours': h,
            'print_time_str': self.total_print_time_str,
        }

    @property
    def total_print_time_str(self):
        """Tiempo de fabricación acumulado formateado."""
        items = list(self.items.all())
        if items:
            mins = sum(((i.print_time_hours or 0.0) * 60 + (i.print_time_minutes or 0)) * (i.quantity or 1) for i in items)
        else:
            mins = ((self.print_time_hours or 0.0) * 60 + (self.print_time_minutes or 0)) * (self.quantity or 1)
        h = int(mins // 60)
        m = int(mins % 60)
        return f"{h}h {m}m"

    @property
    def total_items_count(self):
        """Cantidad total de piezas / unidades en el pedido."""
        items = list(self.items.all())
        if items:
            return sum(i.quantity for i in items)
        return self.quantity or 1

    @property
    def profit_margin_percent(self):
        """Margen de beneficio comercial global en porcentaje."""
        p = self.price or 0
        if p > 0:
            return round(float(self.profit / p) * 100, 1)
        return 0.0

    def update_totals_from_items(self):
        """Recalcula los totales del pedido sumando las métricas de sus piezas."""
        import decimal
        items = list(self.items.all())
        if not items:
            return
        
        total_qty = sum(i.quantity for i in items)
        sum_pieces_p = sum((i.price or decimal.Decimal('0.00')) for i in items)
        total_c = sum((i.total_cost or decimal.Decimal('0.00')) for i in items)
        total_w = sum((i.weight_grams or 0.0) for i in items)
        total_mins = sum(((i.print_time_hours or 0.0) * 60 + (i.print_time_minutes or 0)) for i in items)
        
        h = total_mins // 60
        m = int(total_mins % 60)
        
        # Si incluye IVA, aumenta un 21% al total del pedido
        if self.has_vat:
            total_p = round(sum_pieces_p * decimal.Decimal('1.21'), 2)
        else:
            total_p = sum_pieces_p

        if len(items) == 1:
            desc = items[0].description
            prod = items[0].product
            u_price = round(total_p / total_qty, 2) if total_qty > 0 else items[0].unit_price
            u_cost = items[0].unit_cost
        else:
            desc = " + ".join(i.description for i in items[:3]) + (f" (+{len(items)-3} más)" if len(items) > 3 else "")
            prod = None
            u_price = round(total_p / total_qty, 2) if total_qty > 0 else decimal.Decimal('0.00')
            u_cost = round(total_c / total_qty, 2) if total_qty > 0 else decimal.Decimal('0.00')

        Order.objects.filter(pk=self.pk).update(
            quantity=total_qty,
            price=total_p,
            total_cost=total_c,
            weight_grams=total_w,
            print_time_hours=h,
            print_time_minutes=m,
            description=desc,
            product=prod,
            unit_price=u_price,
            unit_cost=u_cost
        )
        self.refresh_from_db()

    def __str__(self):
        return f"Pedido #{self.id} - {self.description} ({self.client_name})"

# =====================================================================
# MODELO: OrderItem
# Propósito: Representa una pieza individual dentro de un pedido (Order).
# Permite que un pedido contenga múltiples piezas independientes con su
# propio coste, precio, peso, tiempo y estado en el flujo Kanban.
# =====================================================================
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=250, help_text="Nombre o descripción de la pieza")
    quantity = models.IntegerField(default=1, help_text="Cantidad de esta pieza")
    
    # Métricas de fabricación individuales por unidad
    weight_grams = models.FloatField(null=True, blank=True, default=0.0, help_text="Peso en gramos (por unidad)")
    print_time_hours = models.FloatField(null=True, blank=True, default=0.0, help_text="Horas de impresión (por unidad)")
    print_time_minutes = models.IntegerField(null=True, blank=True, default=0, help_text="Minutos de impresión (por unidad)")
    extra_costs = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00, help_text="Costes extra (€)")
    
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00, help_text="Coste unitario (€)")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Coste total (€)")
    
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00, help_text="Precio unitario (€)")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Precio total cobrado (€)")
    
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default='Presupuestado')
    notes = models.TextField(blank=True, null=True, default='', help_text="Notas o especificaciones de la pieza")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_notes(self):
        """Devuelve las notas de la pieza o del pedido si es pieza única."""
        if self.notes and self.notes.strip():
            return self.notes.strip()
        if self.order and self.order.notes and self.order.notes.strip():
            # Si el pedido tiene notas y es la única pieza del pedido
            try:
                if len(self.order.items.all()) <= 1:
                    return self.order.notes.strip()
            except Exception:
                if self.order.items.count() <= 1:
                    return self.order.notes.strip()
        return ''

    def calculate_unit_cost(self):
        """Calcula el coste de producción por unidad según peso, tiempo y consumibles."""
        w = float(self.weight_grams or 0)
        h = float(self.print_time_hours or 0)
        m = float(self.print_time_minutes or 0)
        extra = float(self.extra_costs or 0)
        
        total_hours = h + (m / 60)
        if w > 0 and total_hours > 0:
            cost_filament = 0.02 * w
            cost_energy = 0.15 * 0.12 * total_hours
            cost_wear = 0.30 * total_hours
            cost_subtotal = cost_filament + cost_energy + cost_wear
            error_margin = cost_subtotal * 0.15
            return round(cost_subtotal + error_margin + extra, 2)
        elif self.product:
            return float(self.product.calculate_production_cost())
        return 0.0

    def save(self, *args, **kwargs):
        import decimal
        qty = decimal.Decimal(str(self.quantity or 1))
        
        if self.unit_price is not None:
            self.unit_price = decimal.Decimal(str(self.unit_price))
        if self.price is not None:
            self.price = decimal.Decimal(str(self.price))
        if self.unit_cost is not None:
            self.unit_cost = decimal.Decimal(str(self.unit_cost))
        if self.total_cost is not None:
            self.total_cost = decimal.Decimal(str(self.total_cost))
        if self.extra_costs is not None:
            self.extra_costs = decimal.Decimal(str(self.extra_costs))
            
        calc_cost = self.calculate_unit_cost()
        if calc_cost > 0:
            self.unit_cost = decimal.Decimal(str(calc_cost))
        elif self.unit_cost is None:
            self.unit_cost = decimal.Decimal('0.00')
            
        if (self.total_cost is None or self.total_cost == 0) and self.unit_cost:
            self.total_cost = self.unit_cost * qty
            
        if self.unit_price is not None and self.unit_price > 0:
            if self.price is None or self.price == 0:
                self.price = self.unit_price * qty
        elif self.price is not None and self.price > 0:
            if self.unit_price is None or self.unit_price == 0:
                self.unit_price = round(self.price / qty, 2)
                
        super().save(*args, **kwargs)
        if self.order_id:
            self.order.update_totals_from_items()

    @property
    def profit(self):
        """Ganancia neta generada por esta pieza."""
        import decimal
        p = decimal.Decimal(str(self.price or 0))
        c = decimal.Decimal(str(self.total_cost or 0))
        return p - c

    def __str__(self):
        return f"{self.quantity}x {self.description} (Pedido #{self.order_id})"

# =====================================================================
# MODELO: Review
# Propósito: Almacenar valoraciones y opiniones de los clientes.
# =====================================================================
class Review(models.Model):
    client_name = models.CharField(max_length=150, help_text="Nombre del cliente")
    text = models.TextField(help_text="Texto de la valoración")
    rating = models.PositiveSmallIntegerField(default=5, help_text="Puntuación (1-5 estrellas)")
    is_active = models.BooleanField(default=True, help_text="¿Mostrar en la web pública?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client_name} - {self.rating} estrellas"

# =====================================================================
# MODELO: Cart y CartItem
# Propósito: Funcionalidad del carrito de compras para usuarios.
# =====================================================================
class Cart(models.Model):
    session_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    def __str__(self):
        return f"Cart {self.id} ({self.session_key})"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def unit_price(self):
        return self.product.sale_price if (self.product.is_on_sale and self.product.sale_price) else self.product.price

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.title}"
