from django.contrib import admin
from .models import Category, Product, ProductImage, Quote, QuoteItem, Order, OrderItem, Review

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_categories', 'price', 'is_on_sale', 'is_active')
    list_filter = ('categories', 'is_on_sale', 'is_active')
    search_fields = ('title', 'description')
    filter_horizontal = ('categories',)
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline]

    def display_categories(self, obj):
        return ", ".join([c.name for c in obj.categories.all()]) or "-"
    display_categories.short_description = 'Categorías'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'client_name', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    inlines = [QuoteItemInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'client_name', 'quantity', 'price', 'deposit_amount', 'deposit_method', 'final_payment_method', 'profit', 'status', 'platform', 'shipping', 'order_date')
    list_filter = ('status', 'platform', 'shipping', 'order_date')
    search_fields = ('description', 'client_name', 'notes')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'description', 'quantity', 'price', 'total_cost', 'profit', 'status')
    list_filter = ('status', 'order__platform')
    search_fields = ('description', 'order__client_name')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'rating', 'is_active', 'created_at')
    list_filter = ('rating', 'is_active')
    search_fields = ('client_name', 'text')
