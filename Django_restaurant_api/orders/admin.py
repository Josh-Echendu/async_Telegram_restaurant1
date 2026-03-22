from django.contrib import admin
from .models import Category, Product, ProductImages, Cart, OrderBatch, OrderBatchItem, Restaurant, CheckoutSession


class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['rid', 'name', 'description', 'image']

class ProductAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'title', 'product_image', 'price', 'category', 'in_stock']

class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category_image', 'restaurant']

class ProductImagesAdmin(admin.ModelAdmin):
    list_display = ['product', 'product_image', 'date']

class CartAdmin(admin.ModelAdmin):
    list_display = ['telegram_user', 'product__title', 'product_image', 'quantity', 'date_added']

class OrderBatchAdmin(admin.ModelAdmin):
    list_display = ['telegram_user__telegram_id', 'telegram_user__username', 'bid', 'total_price', 'payment_status', 'date_created']

class OrderBatchItemAdmin(admin.ModelAdmin):
    list_display = ['batch', 'product__title', 'product_image', 'quantity', 'price', 'multiply_price']

class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'telegram_user__username', 'restaurant__name', 'is_active', 'payment_in_progress']


admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(ProductImages, ProductImagesAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(OrderBatch, OrderBatchAdmin)
admin.site.register(OrderBatchItem, OrderBatchItemAdmin)
admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(CheckoutSession, CheckoutSessionAdmin)
