from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category

class StaticViewSitemap(Sitemap):
    """Sitemap para las vistas estáticas públicas principales."""
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ['catalog', 'about_us', 'custom_order']

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == 'catalog':
            return 1.0
        elif item == 'about_us':
            return 0.8
        return 0.8


class ProductSitemap(Sitemap):
    """Sitemap para todas las fichas de productos activas."""
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Product.objects.filter(is_active=True).order_by('-created_at')

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return obj.get_absolute_url()


class CategorySitemap(Sitemap):
    """Sitemap para las categorías con piezas activas."""
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Category.objects.filter(products__is_active=True).distinct().order_by('name')

    def location(self, obj):
        return reverse('catalog') + f"?category={obj.slug}"

