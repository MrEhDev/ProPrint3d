"""
URL configuration for proprint3d_project project.
"""
import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import TemplateView
from django.http import FileResponse, HttpResponse
from django.contrib.sitemaps.views import sitemap
from proprint3d.sitemaps import StaticViewSitemap, ProductSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
}

def clean_sitemap_view(request, **kwargs):
    response = sitemap(request, **kwargs)
    if hasattr(response, 'headers') and 'X-Robots-Tag' in response.headers:
        del response.headers['X-Robots-Tag']
    elif response.has_header('X-Robots-Tag'):
        del response['X-Robots-Tag']
    return response

def root_favicon_view(request):
    """Sirve directamente el favicon.ico con 200 OK para Googlebot y navegadores sin redirecciones."""
    ico_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'favicon.ico')
    if os.path.exists(ico_path):
        return FileResponse(open(ico_path, 'rb'), content_type='image/x-icon')
    return HttpResponse(status=404)

# Configuración principal de URLs
# Incluye las rutas de la app 'proprint3d', sitemap, robots.txt y favicon
urlpatterns = [
    # SEO & Indexación Google y Agentes de IA
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain"), name='robots_file'),
    path('llms.txt', TemplateView.as_view(template_name="llms.txt", content_type="text/plain; charset=utf-8"), name='llms_file'),
    path('sitemap.xml', clean_sitemap_view, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('favicon.ico', root_favicon_view, name='root_favicon'),

    # Panel de administración protegido con URL oculta no estándar
    path('gestion-taller/', admin.site.urls),
    path('', include('proprint3d.urls')), # Rutas de nuestra app principal
]

# Servir archivos estáticos y media durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
