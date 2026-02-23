import os
from rest_framework import serializers
from .models import Product, Category, Cart, OrderBatch, OrderBatchItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['cid', 'title', 'category_image']

class ProductSerializer(serializers.ModelSerializer):
    # category = Category()
    cart_quantity = serializers.IntegerField(read_only=True)

    # cart_items = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'title', 'price', 'image', 'cart_quantity']

    # def get_image(self, obj):
    #     if obj.image:
    #         BASE_URL = os.getenv("BASE_URL")
    #         return f"{BASE_URL}{obj.image.url}"
    #     return None

    # def get_cart_items(self, obj):
    #     cart = Cart.objects.filter(product=obj)
    #     return CartSerializer(cart, many=True).data
    
        # serializer = self.get_serializer(self.get_queryset(), many=True).data
        # print("Serialized data:", serializer)

class CartSerializer(serializers.ModelSerializer):
    product_price = serializers.DecimalField(source='product.price', read_only=True, max_digits=10, decimal_places=2)
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    total_price = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    
    class Meta:
        model = Cart
        fields = ['product_id', 'quantity', 'product_title', 'product_price', 'product_image', 'total_price']

class OrderBatchSerializer(serializers.ModelSerializer):
    # items = OrderBatchItemSerializer(many=True, read_only=True)

    class Meta:
        model = OrderBatch
        fields = '__all__'
