from rest_framework import serializers
from orders.serializers import ProductSerializer, OrderBatchSerializer
from userAuths.serializers import TelegramUserSerializer


class DashboardSerializer(serializers.Serializer):
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_orders_count = serializers.IntegerField()
    all_products = ProductSerializer(many=True)
    new_customers = TelegramUserSerializer(many=True)
    latest_orders = OrderBatchSerializer(many=True)
