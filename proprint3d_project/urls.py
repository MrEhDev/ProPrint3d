"""
URL configuration for proprint3d_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Configuración principal de URLs
# Incluye las rutas de la app 'proprint3d' y del panel de administración
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('proprint3d.urls')), # Rutas de nuestra app principal
]

# Servir archivos estáticos y media durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
