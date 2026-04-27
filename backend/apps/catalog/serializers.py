from rest_framework import serializers
from .models import Brand, Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "parent")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name")


class ProductVariantSerializer(serializers.ModelSerializer):
    available_quantity = serializers.IntegerField(source="inventory_record.quantity_available", read_only=True)

    class Meta:
        model = ProductVariant
        fields = ("id", "sku", "price", "is_active", "available_quantity")


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "description", "category", "brand", "is_active", "variants")
