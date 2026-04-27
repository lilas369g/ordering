from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='variant.sku', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'sku', 'quantity', 'unit_price')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id',
            'status',
            'total_amount',
            'customer_name',
            'phone_number',
            'shipping_address',
            'province',
            'items',
            'created_at',
        )


class CheckoutSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    shipping_address = serializers.CharField(max_length=255)
    province = serializers.CharField(max_length=100)
