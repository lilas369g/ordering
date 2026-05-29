from decimal import Decimal
import logging
from django.db import transaction
from django.db.models import F
from apps.cart.models import Cart, CartItem, CartStatus
from apps.inventory.models import InventoryRecord, StockMovement, StockMovementType
from .models import Order, OrderItem, OrderStatus

logger = logging.getLogger(__name__)

class CheckoutError(ValueError):
    pass

# ══════════════════════════════════════════════════════════
# الطريقة 1: Pessimistic Locking (كود رفيقتك الأصلي - Baseline)
# ══════════════════════════════════════════════════════════
@transaction.atomic
def checkout_cart_pessimistic(customer, *, customer_name: str, phone_number: str, shipping_address: str, province: str) -> Order:
    logger.info(f"[Pessimistic] Starting checkout for user {customer.id}")
    
    cart = (
        Cart.objects.select_for_update()
        .filter(customer=customer, status=CartStatus.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if not cart:
        raise CheckoutError("No active cart.")

    items = list(
        CartItem.objects.select_related("variant", "variant__product")
        .filter(cart=cart)
        .order_by("id")
    )
    if not items:
        raise CheckoutError("Cart is empty.")

    variant_ids = [item.variant_id for item in items]
    # Lock Ordering لمنع Deadlock
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
            raise CheckoutError(f"Not enough stock for {item.variant.sku}. Available: {available}")

    total_amount = sum((item.unit_price_snapshot * item.quantity for item in items), Decimal("0.00"))
    order = Order.objects.create(
        customer=customer, status=OrderStatus.PENDING, total_amount=total_amount,
        customer_name=customer_name, phone_number=phone_number,
        shipping_address=shipping_address, province=province,
    )

    OrderItem.objects.bulk_create([
        OrderItem(order=order, variant=item.variant, quantity=item.quantity, unit_price=item.unit_price_snapshot)
        for item in items
    ])

    stock_movements = []
    for item in items:
        inventory = inventory_by_variant_id[item.variant_id]
        inventory.quantity_available -= item.quantity
        inventory.save(update_fields=["quantity_available", "updated_at"])
        stock_movements.append(
            StockMovement(variant=item.variant, movement_type=StockMovementType.SALE, quantity=-item.quantity, note=f"Order #{order.id}")
        )

    StockMovement.objects.bulk_create(stock_movements)
    CartItem.objects.filter(cart=cart).delete()
    cart.status = CartStatus.ORDERED
    cart.save(update_fields=["status", "updated_at"])
    
    logger.info(f"[Pessimistic] SUCCESS Order#{order.id}")
    return order


# ══════════════════════════════════════════════════════════
# الطريقة 2: Optimistic Locking (إضافتك - باستخدام version)
# ══════════════════════════════════════════════════════════
def checkout_cart_optimistic(customer, *, customer_name: str, phone_number: str, shipping_address: str, province: str, max_retries=3) -> Order:
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        logger.info(f"[Optimistic] Attempt #{attempt} for user {customer.id}")
        
        try:
            with transaction.atomic():
                cart = Cart.objects.filter(customer=customer, status=CartStatus.ACTIVE).order_by("-created_at").first()
                if not cart: raise CheckoutError("No active cart.")

                items = list(CartItem.objects.select_related("variant", "variant__product").filter(cart=cart).order_by("id"))
                if not items: raise CheckoutError("Cart is empty.")

                variant_ids = [item.variant_id for item in items]
                # قراءة بدون قفل
                inventory_by_variant_id = {
                    record.variant_id: record
                    for record in InventoryRecord.objects.filter(variant_id__in=variant_ids)
                }

                for item in items:
                    inventory = inventory_by_variant_id.get(item.variant_id)
                    available = inventory.quantity_available if inventory else 0
                    if item.quantity > available:
                        raise CheckoutError(f"Not enough stock for {item.variant.sku}.")

                total_amount = sum((item.unit_price_snapshot * item.quantity for item in items), Decimal("0.00"))
                order = Order.objects.create(
                    customer=customer, status=OrderStatus.PENDING, total_amount=total_amount,
                    customer_name=customer_name, phone_number=phone_number,
                    shipping_address=shipping_address, province=province,
                )
                OrderItem.objects.bulk_create([
                    OrderItem(order=order, variant=item.variant, quantity=item.quantity, unit_price=item.unit_price_snapshot)
                    for item in items
                ])

                # محاولة التحديث مشروطة بالـ version
                conflict = False
                stock_movements = []
                for item in items:
                    inventory = inventory_by_variant_id[item.variant_id]
                    updated_rows = InventoryRecord.objects.filter(
                        variant_id=item.variant_id,
                        version=inventory.version # الشرط الحاسم
                    ).update(
                        quantity_available=F('quantity_available') - item.quantity,
                        version=F('version') + 1
                    )

                    if updated_rows == 0:
                        # شخص ثاني عدل المخزون قبلنا!
                        logger.warning(f"[Optimistic] CONFLICT on variant {item.variant_id}!")
                        conflict = True
                        break
                    
                    stock_movements.append(
                        StockMovement(variant=item.variant, movement_type=StockMovementType.SALE, quantity=-item.quantity, note=f"Order #{order.id}")
                    )

                if conflict:
                    raise Exception("Optimistic Lock Conflict - Retry") # لنجبر الـ transaction على الـ rollback

                StockMovement.objects.bulk_create(stock_movements)
                CartItem.objects.filter(cart=cart).delete()
                cart.status = CartStatus.ORDERED
                cart.save(update_fields=["status", "updated_at"])
                
                logger.info(f"[Optimistic] SUCCESS Order#{order.id} on attempt {attempt}")
                return order

        except CheckoutError:
            raise # أخطاء المستخدم لا نعيد محاولتها
        except Exception as e:
            if "Optimistic Lock Conflict" in str(e) and attempt < max_retries:
                continue # نعيد المحاولة
            raise CheckoutError("Checkout failed due to high demand. Please try again.")
    
    raise CheckoutError("Failed after maximum retries.")


# ══════════════════════════════════════════════════════════
# الطريقة 3: الحل الذكي (Atomic F() Expression - بدون قفل نهائياً!)
# ══════════════════════════════════════════════════════════
@transaction.atomic
def checkout_cart_atomic(customer, *, customer_name: str, phone_number: str, shipping_address: str, province: str) -> Order:
    logger.info(f"[Atomic F()] Starting checkout for user {customer.id}")
    
    cart = Cart.objects.filter(customer=customer, status=CartStatus.ACTIVE).order_by("-created_at").first()
    if not cart: raise CheckoutError("No active cart.")

    items = list(CartItem.objects.select_related("variant", "variant__product").filter(cart=cart).order_by("id"))
    if not items: raise CheckoutError("Cart is empty.")

    total_amount = sum((item.unit_price_snapshot * item.quantity for item in items), Decimal("0.00"))
    order = Order.objects.create(
        customer=customer, status=OrderStatus.PENDING, total_amount=total_amount,
        customer_name=customer_name, phone_number=phone_number,
        shipping_address=shipping_address, province=province,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, variant=item.variant, quantity=item.quantity, unit_price=item.unit_price_snapshot)
        for item in items
    ])

    stock_movements = []
    for item in items:
        # خصم مباشر بشرط كفاية المخزون - بخطوة واحدة على مستوى الداتابيز!
        updated_rows = InventoryRecord.objects.filter(
            variant_id=item.variant_id,
            quantity_available__gte=item.quantity # المخزون أكبر أو يساوي المطلوب
        ).update(
            quantity_available=F('quantity_available') - item.quantity
        )

        if updated_rows == 0:
            # لو رجع 0، إما المخزون ما كفى أو حد ثاني سبقنا
            raise CheckoutError(f"Stock changed for {item.variant.sku}. Please try again.")
        
        stock_movements.append(
            StockMovement(variant=item.variant, movement_type=StockMovementType.SALE, quantity=-item.quantity, note=f"Order #{order.id}")
        )

    StockMovement.objects.bulk_create(stock_movements)
    CartItem.objects.filter(cart=cart).delete()
    cart.status = CartStatus.ORDERED
    cart.save(update_fields=["status", "updated_at"])
    
    logger.info(f"[Atomic F()] SUCCESS Order#{order.id}")
    return order


# دالة التوجيه (Router) - عشان نختار أي طريقة نستخدمها
def checkout_cart(customer, **kwargs) -> Order:
    # غيّري هاد المتغير لتجربة الطرق المختلفة أمام المعيد
    STRATEGY = "atomic" # ممكن تكون: "pessimistic", "optimistic", "atomic"
    
    if STRATEGY == "pessimistic":
        return checkout_cart_pessimistic(customer, **kwargs)
    elif STRATEGY == "optimistic":
        return checkout_cart_optimistic(customer, **kwargs)
    elif STRATEGY == "atomic":
        return checkout_cart_atomic(customer, **kwargs)
    else:
        raise ValueError("Invalid checkout strategy")