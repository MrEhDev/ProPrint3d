from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    Branch, UserProfile, Category, Product, ProductImage,
    Quote, QuoteItem, Order, OrderItem, Review, Customer
)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'whatsapp', 'phone', 'email', 'greeting_name', 'is_main', 'is_active')
    list_filter = ('is_main', 'is_active')
    search_fields = ('name', 'slug', 'whatsapp', 'phone', 'email')
    prepopulated_fields = {'slug': ('name',)}


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = 'Sede Asignada'
    verbose_name_plural = 'Sede Asignada'
    extra = 0
    fields = ('branch',)


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

    def get_inline_instances(self, request, obj=None):
        # Al crear un nuevo usuario no mostramos inlines para evitar errores de formulario
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'phone', 'city', 'province', 'platform', 'total_orders', 'total_spent', 'created_at')
    list_filter = ('branch', 'platform', 'province', 'created_at')
    search_fields = ('name', 'phone', 'email', 'address', 'city', 'postal_code', 'notes')
    ordering = ('name',)

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
    list_display = ('id', 'client_name', 'branch', 'total_price', 'status', 'created_at')
    list_filter = ('branch', 'status', 'created_at')
    inlines = [QuoteItemInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'branch', 'description', 'client_name', 'quantity', 'price', 'deposit_amount', 'deposit_method', 'final_payment_method', 'profit', 'status', 'platform', 'shipping', 'order_date')
    list_filter = ('branch', 'status', 'platform', 'shipping', 'order_date')
    search_fields = ('description', 'client_name', 'client_phone', 'client_email', 'client_contact', 'tracking_number', 'notes')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'description', 'quantity', 'price', 'total_cost', 'profit', 'status')
    list_filter = ('status', 'order__platform')
    search_fields = ('description', 'order__client_name')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'rating', 'source', 'client_details', 'time_ago', 'is_active', 'created_at')
    list_filter = ('rating', 'source', 'is_active')
    search_fields = ('client_name', 'text', 'client_details')
