from django.contrib import admin
from .models import Category, Product, ProductImage, Quote, QuoteItem, Order, Review

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'is_on_sale', 'is_active')
    list_filter = ('category', 'is_on_sale', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline]

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

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'client_name', 'price', 'profit', 'status', 'platform', 'shipping', 'order_date')
    list_filter = ('status', 'platform', 'shipping', 'order_date')
    search_fields = ('description', 'client_name')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'rating', 'is_active', 'created_at')
    list_filter = ('rating', 'is_active')
    search_fields = ('client_name', 'text')
