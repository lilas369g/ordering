from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.catalog.models import ProductVariant

from .models import Cart, CartItem, CartStatus


def _ensure_session(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def get_or_create_active_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(
            customer=request.user,
            status=CartStatus.ACTIVE,
            defaults={"expires_at": timezone.now() + timedelta(days=3)},
        )
        return cart

    session_key = _ensure_session(request)
    cart, _ = Cart.objects.get_or_create(
        session_key=session_key,
        status=CartStatus.ACTIVE,
        defaults={"expires_at": timezone.now() + timedelta(days=3)},
    )
    return cart


@transaction.atomic
def add_variant_to_cart(cart: Cart, variant_id: int, quantity: int = 1) -> CartItem:
    variant = get_object_or_404(
        ProductVariant.objects.select_related("inventory_record", "product"),
        pk=variant_id,
        is_active=True,
        product__is_active=True,
    )
    inventory = getattr(variant, "inventory_record", None)
    available = inventory.quantity_available if inventory else 0
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={
            "quantity": 0,
            "unit_price_snapshot": variant.price,
        },
    )
    new_quantity = cart_item.quantity + max(quantity, 1)
    if new_quantity > available:
        raise ValueError(f"Only {available} units available for {variant.sku}.")

    cart_item.quantity = new_quantity
    cart_item.unit_price_snapshot = variant.price
    cart_item.save(update_fields=["quantity", "unit_price_snapshot", "updated_at"])
    return cart_item


@transaction.atomic
def update_cart_item_quantity(cart: Cart, item_id: int, quantity: int):
    item = get_object_or_404(CartItem.objects.select_related("variant__inventory_record"), pk=item_id, cart=cart)
    if quantity <= 0:
        item.delete()
        return None

    available = getattr(item.variant.inventory_record, "quantity_available", 0)
    if quantity > available:
        raise ValueError(f"Only {available} units available for {item.variant.sku}.")

    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item
