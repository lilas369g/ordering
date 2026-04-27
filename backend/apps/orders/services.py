from decimal import Decimal

from django.db import transaction

from apps.cart.models import Cart, CartItem, CartStatus
from apps.inventory.models import InventoryRecord, StockMovement, StockMovementType

from .models import Order, OrderItem, OrderStatus


class CheckoutError(ValueError):
    pass


@transaction.atomic
def checkout_cart(customer, *, customer_name: str, phone_number: str, shipping_address: str, province: str) -> Order:
    cart = (
        Cart.objects.select_for_update()
        .filter(customer=customer, status=CartStatus.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if not cart:
        raise CheckoutError("لا توجد سلة فعالة لهذا المستخدم.")

    items = list(
        CartItem.objects.select_related("variant", "variant__product")
        .filter(cart=cart)
        .order_by("id")
    )
    if not items:
        raise CheckoutError("السلة فارغة.")

    variant_ids = [item.variant_id for item in items]
    inventory_by_variant_id = {
        record.variant_id: record
        for record in InventoryRecord.objects.select_for_update()
        .filter(variant_id__in=variant_ids)
        .order_by("variant_id")
    }

    for item in items:
        inventory = inventory_by_variant_id.get(item.variant_id)
        available = inventory.quantity_available if inventory else 0
        if item.quantity > available:
            raise CheckoutError(
                f"الكمية المتوفرة من {item.variant.sku} هي {available} فقط."
            )

    total_amount = sum(
        (item.unit_price_snapshot * item.quantity for item in items),
        Decimal("0.00"),
    )
    order = Order.objects.create(
        customer=customer,
        status=OrderStatus.PENDING,
        total_amount=total_amount,
        customer_name=customer_name,
        phone_number=phone_number,
        shipping_address=shipping_address,
        province=province,
    )

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
            )
            for item in items
        ]
    )

    stock_movements = []
    for item in items:
        inventory = inventory_by_variant_id[item.variant_id]
        inventory.quantity_available -= item.quantity
        inventory.save(update_fields=["quantity_available", "updated_at"])
        stock_movements.append(
            StockMovement(
                variant=item.variant,
                movement_type=StockMovementType.SALE,
                quantity=-item.quantity,
                note=f"Order #{order.id}",
            )
        )

    StockMovement.objects.bulk_create(stock_movements)
    CartItem.objects.filter(cart=cart).delete()
    cart.status = CartStatus.ORDERED
    cart.save(update_fields=["status", "updated_at"])

    return order
