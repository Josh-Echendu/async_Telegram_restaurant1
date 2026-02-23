from django.contrib import admin
from .models import Category, Product, ProductImages, Cart, OrderBatch, OrderBatchItem

class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'product_image', 'price', 'category', 'in_stock']

class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category_image']

class ProductImagesAdmin(admin.ModelAdmin):
    list_display = ['product', 'product_image', 'date']

class CartAdmin(admin.ModelAdmin):
    list_display = ['telegram_user', 'product__title', 'product_image', 'quantity', 'date_added']

class OrderBatchAdmin(admin.ModelAdmin):
    list_display = ['telegram_user__telegram_id', 'telegram_user__username', 'bid', 'total_price', 'payment_status', 'date_created']

class OrderBatchItemAdmin(admin.ModelAdmin):
    list_display = ['batch', 'product__title', 'product_image', 'quantity', 'price', 'multiply_price']

admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(ProductImages, ProductImagesAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(OrderBatch, OrderBatchAdmin)
admin.site.register(OrderBatchItem, OrderBatchItemAdmin)
