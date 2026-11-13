"""
URL configuration for proprint3d_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import TemplateView, RedirectView
from django.contrib.sitemaps.views import sitemap
from proprint3d.sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap

sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
}

def clean_sitemap_view(request, **kwargs):
    response = sitemap(request, **kwargs)
    if hasattr(response, 'headers') and 'X-Robots-Tag' in response.headers:
        del response.headers['X-Robots-Tag']
    elif response.has_header('X-Robots-Tag'):
        del response['X-Robots-Tag']
    return response

# Configuración principal de URLs
# Incluye las rutas de la app 'proprint3d', sitemap, robots.txt y favicon
urlpatterns = [
    # SEO & Indexación Google y Agentes de IA
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain"), name='robots_file'),
    path('llms.txt', TemplateView.as_view(template_name="llms.txt", content_type="text/plain; charset=utf-8"), name='llms_file'),
    path('sitemap.xml', clean_sitemap_view, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),

    # Panel de administración protegido con URL oculta no estándar
    path('gestion-taller/', admin.site.urls),
    path('', include('proprint3d.urls')), # Rutas de nuestra app principal
]

# Servir archivos estáticos y media durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
