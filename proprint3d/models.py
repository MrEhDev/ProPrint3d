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
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
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
    
    # Estados y auditoría
    is_active = models.BooleanField(default=True, help_text="¿Visible en el catálogo?")
    created_at = models.DateTimeField(auto_now_add=True)

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
            cost_wear = 0.025 * total_hours
            
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
        ('Pendiente', 'Pendiente'),
        ('Realizado', 'Realizado'),
        ('Pdt de envío', 'Pdt de envío'),
        ('Pdt. entrega', 'Pdt. entrega'),
        ('Enviado', 'Enviado'),
        ('Entregado', 'Entregado'),
        ('Cobrado', 'Cobrado'),
        ('Cancelado', 'Cancelado')
    ]
    
    PLATFORM_CHOICES = [
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

    order_date = models.DateField(help_text="Fecha de Pedido")
    quantity = models.IntegerField(default=1, help_text="Cantidad")
    
    # Puede estar linkado a un producto, pero permitimos nombre libre si es un custom
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=250, blank=True, null=True, help_text="Descripción del Pedido (Ej. Fiat Panda Rally)")
    
    client_name = models.CharField(max_length=150, help_text="Nombre de la Persona")
    
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio Final Cobrado (€)")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Coste Total Producción (€)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pendiente')
    deadline = models.DateField(null=True, blank=True, help_text="Fecha límite")
    
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, default='Wallapop Elyest')
    shipping = models.CharField(max_length=50, choices=SHIPPING_CHOICES, default='Inpost')
    
    notes = models.TextField(blank=True, null=True, help_text="Notas adicionales")

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-completar descripción si hay producto y no hay descripción manual
        if self.product and not self.description:
            self.description = self.product.title
            
        # Auto-completar precio si no se ha introducido y hay producto
        if self.product and (self.price is None or self.price == 0):
            self.price = self.product.price * self.quantity
            
        # Auto-completar coste de producción si está vacío y hay producto
        if self.product and (self.total_cost is None or self.total_cost == 0):
            import decimal
            # Convert float cost to decimal
            cost_per_unit = self.product.calculate_production_cost()
            self.total_cost = decimal.Decimal(str(cost_per_unit)) * self.quantity
            
        super().save(*args, **kwargs)

    @property
    def profit(self):
        """Calcula la ganancia real descontando el coste de producción."""
        if self.price and self.total_cost is not None:
            return self.price - self.total_cost
        return 0

    def __str__(self):
        return f"Pedido #{self.id} - {self.description} ({self.client_name})"

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
