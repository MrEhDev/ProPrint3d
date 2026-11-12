from django.urls import path
from . import views

# =====================================================================
# MÓDULO: urls.py (App)
# Propósito: Enrutar las URLs a las vistas correspondientes.
# =====================================================================
urlpatterns = [
    # Catálogo público
    path('', views.catalog_view, name='catalog'),
    path('quienes-somos/', views.about_view, name='about_us'),
    path('trofeos-medallas-personalizadas/', views.trophies_medals_view, name='trophies_medals'),
    path('trofeos-medallas/api/add/', views.add_trophy_gallery_item_api, name='add_trophy_gallery_item_api'),
    path('trofeos-medallas/api/<int:item_id>/delete/', views.delete_trophy_gallery_item_api, name='delete_trophy_gallery_item_api'),
    path('cambiar-sede/<slug:branch_slug>/', views.switch_branch_view, name='switch_branch'),
    
    # Formulario personalizado
    path('custom-order/', views.custom_order_view, name='custom_order'),
    
    # Detalle de un producto (slug)
    path('product/<slug:slug>/', views.product_detail_view, name='product_detail'),
    path('product/<slug:slug>/download-model/', views.download_product_model_file, name='download_product_model'),
    
    # Editar un producto (slug)
    path('product/<slug:slug>/edit/', views.product_edit_view, name='product_edit'),
    
    # Dashboard privado de administración (Calculadora, Scraper, etc)
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    
    # Endpoint para generar PDF de presupuesto
    path('quote/<int:quote_id>/pdf/', views.generate_quote_pdf_view, name='generate_quote_pdf'),
    
    # Creador de Presupuestos
    path('quotes/build/', views.quote_builder_view, name='quote_builder'),
    
    # Autenticación Admin Integrada
    path('login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.admin_logout_view, name='admin_logout'),

    # CRM de Pedidos (admite /crm/ y /CRM/)
    path('crm/', views.crm_dashboard_view, name='crm_dashboard'),
    path('CRM/', views.crm_dashboard_view),
    path('crm/catalogo-pdf/', views.generate_category_catalog_pdf_view, name='generate_catalog_pdf'),
    path('crm/catalogo-pdf/<slug:category_slug>/', views.generate_category_catalog_pdf_view, name='generate_catalog_pdf_category'),
    path('crm/order/new/', views.order_create_view, name='order_create'),
    path('crm/order/<int:order_id>/quote-pdf/', views.generate_order_quote_pdf_view, name='generate_order_quote_pdf'),
    path('crm/order/<int:order_id>/thermal-label/', views.order_thermal_label_view, name='order_thermal_label'),
    path('crm/api/order/<int:order_id>/status/', views.update_order_status_api, name='update_order_status_api'),
    path('crm/api/order/<int:order_id>/cost/', views.update_order_cost_api, name='update_order_cost_api'),
    path('crm/api/order/<int:order_id>/dates/', views.update_order_dates_api, name='update_order_dates_api'),
    path('crm/api/order/<int:order_id>/payment/', views.update_order_payment_api, name='update_order_payment_api'),
    path('crm/api/order/<int:order_id>/shipping/', views.api_update_order_shipping, name='api_update_order_shipping'),
    path('crm/api/order/<int:order_id>/edit/', views.update_order_full_api, name='update_order_full_api'),
    path('crm/api/order/<int:order_id>/delete/', views.delete_order_api, name='delete_order_api'),
    path('crm/api/item/<int:item_id>/status/', views.update_item_status_api, name='update_item_status_api'),
    path('crm/api/item/<int:item_id>/cost/', views.update_item_cost_api, name='update_item_cost_api'),
    path('crm/api/item/<int:item_id>/progress/', views.update_item_progress_api, name='update_item_progress_api'),
    
    # APIs Clientes y Envíos Correos
    path('crm/api/customers/search/', views.api_customers_search, name='api_customers_search'),
    path('crm/api/customers/save/', views.api_customer_save, name='api_customer_save'),
    path('crm/api/shipping/calculate/', views.api_calculate_shipping_rates, name='api_calculate_shipping_rates'),
    path('crm/api/postal-code/<str:cp>/', views.api_postal_code_lookup, name='api_postal_code_lookup'),
    
    # Inventario de Filamentos (Spoolman nativo)
    path('crm/filamentos/', views.filament_inventory_view, name='filament_inventory'),
    path('crm/filamentos/api/adjust-stock/', views.api_filament_adjust_stock, name='api_filament_adjust_stock'),
    path('crm/filamentos/api/save/', views.api_filament_save, name='api_filament_save'),
    path('crm/filamentos/api/list/', views.api_filament_list, name='api_filament_list'),
    path('crm/filamentos/api/delete/<int:filament_id>/', views.api_filament_delete, name='api_filament_delete'),
    
    # APIs rápidas de producto
    path('api/product/check-title/', views.check_product_title_api, name='check_product_title_api'),
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
