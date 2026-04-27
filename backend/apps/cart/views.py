from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AddToCartSerializer, CartSerializer, UpdateCartItemSerializer
from .services import add_variant_to_cart, get_or_create_active_cart, update_cart_item_quantity


class CartDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cart = get_or_create_active_cart(request)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class AddToCartApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_or_create_active_cart(request)
        try:
            item = add_variant_to_cart(cart, **serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Added to cart.", "item_id": item.id}, status=status.HTTP_201_CREATED)


class UpdateCartItemApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, item_id):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_or_create_active_cart(request)
        try:
            item = update_cart_item_quantity(cart, item_id=item_id, quantity=serializer.validated_data["quantity"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Updated.", "item_id": getattr(item, "id", None)})


def cart_page(request):
    cart = get_or_create_active_cart(request)
    items = cart.items.select_related("variant__product", "variant__inventory_record").all()
    total = sum(item.unit_price_snapshot * item.quantity for item in items)
    return render(request, "storefront/cart.html", {"cart": cart, "items": items, "total": total})


def add_to_cart_page(request):
    if request.method != "POST":
        return redirect("storefront:product-list")
    cart = get_or_create_active_cart(request)
    variant_id = int(request.POST.get("variant_id", 0))
    quantity = int(request.POST.get("quantity", 1))
    try:
        add_variant_to_cart(cart, variant_id=variant_id, quantity=quantity)
        messages.success(request, "The product was added to your cart.")
    except ValueError as exc:
        messages.error(request, str(exc))
    next_url = request.POST.get("next") or reverse("storefront:product-list")
    return HttpResponseRedirect(next_url)


def update_cart_item_page(request, item_id):
    if request.method != "POST":
        return redirect("storefront:cart-page")
    cart = get_or_create_active_cart(request)
    quantity = int(request.POST.get("quantity", 1))
    try:
        update_cart_item_quantity(cart, item_id=item_id, quantity=quantity)
        messages.success(request, "The cart was updated.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("storefront:cart-page")
