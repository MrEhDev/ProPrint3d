from django.urls import path
from . import views

# =====================================================================
# MÓDULO: urls.py (App)
# Propósito: Enrutar las URLs a las vistas correspondientes.
# =====================================================================
urlpatterns = [
    # Catálogo público
    path('', views.catalog_view, name='catalog'),
    
    # Formulario personalizado
    path('custom-order/', views.custom_order_view, name='custom_order'),
    
    # Detalle de un producto (slug)
    path('product/<slug:slug>/', views.product_detail_view, name='product_detail'),
    
    # Editar un producto (slug)
    path('product/<slug:slug>/edit/', views.product_edit_view, name='product_edit'),
    
    # Dashboard privado de administración (Calculadora, Scraper, etc)
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    
    # Endpoint para generar PDF de presupuesto
    path('quote/<int:quote_id>/pdf/', views.generate_quote_pdf_view, name='generate_quote_pdf'),
    
    # Creador de Presupuestos
    path('quotes/build/', views.quote_builder_view, name='quote_builder'),
    
    # CRM de Pedidos
    path('crm/', views.crm_dashboard_view, name='crm_dashboard'),
    path('crm/order/new/', views.order_create_view, name='order_create'),
    path('crm/api/order/<int:order_id>/status/', views.update_order_status_api, name='update_order_status_api'),
    path('crm/api/order/<int:order_id>/cost/', views.update_order_cost_api, name='update_order_cost_api'),
    
    # APIs rápidas de producto
    path('product/<slug:slug>/toggle-sale/', views.toggle_sale_api, name='toggle_sale_api'),
    path('product/<slug:slug>/toggle-active/', views.toggle_active_api, name='toggle_active_api'),
    path('product/<slug:slug>/delete/', views.product_delete_view, name='product_delete'),
    path('product-image/<int:image_id>/delete/', views.product_image_delete_api, name='product_image_delete'),
    path('crm/api/product/<int:product_id>/price/', views.get_product_price_api, name='get_product_price_api'),
    
    # Carrito de Compras
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart_view, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart_view, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_view, name='update_cart'),
]
