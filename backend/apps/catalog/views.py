from django.shortcuts import render
from rest_framework import generics, permissions

from apps.cart.services import get_or_create_active_cart

from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)


def storefront_product_list(request):
    products = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)
    cart = get_or_create_active_cart(request)
    cart_count = sum(item.quantity for item in cart.items.all())
    return render(request, "storefront/product_list.html", {
        "products": products,
        "cart": cart,
        "cart_count": cart_count,
    })
