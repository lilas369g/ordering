from decimal import Decimal

from rest_framework import serializers

from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="variant.sku", read_only=True)
    product_name = serializers.CharField(source="variant.product.name", read_only=True)
    current_price = serializers.DecimalField(source="variant.price", max_digits=12, decimal_places=2, read_only=True)
    line_total = serializers.SerializerMethodField()
    available_quantity = serializers.IntegerField(source="variant.inventory_record.quantity_available", read_only=True)

    class Meta:
        model = CartItem
        fields = (
            "id",
            "variant",
            "sku",
            "product_name",
            "current_price",
            "unit_price_snapshot",
            "available_quantity",
            "quantity",
            "line_total",
        )

    def get_line_total(self, obj):
        return Decimal(obj.quantity) * obj.unit_price_snapshot


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "status", "expires_at", "items", "total")

    def get_total(self, obj):
        return sum((item.unit_price_snapshot * item.quantity for item in obj.items.all()), Decimal("0.00"))


class AddToCartSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)
