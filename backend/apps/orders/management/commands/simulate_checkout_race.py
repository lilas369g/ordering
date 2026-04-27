from decimal import Decimal
from threading import Barrier, Thread
from time import perf_counter
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.db.models import F

from apps.cart.models import Cart, CartItem, CartStatus
from apps.catalog.models import Brand, Category, Product, ProductVariant
from apps.inventory.models import InventoryRecord
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.orders.services import CheckoutError, checkout_cart
from apps.users.models import UserType

User = get_user_model()


class Command(BaseCommand):
    help = "Print checkout race-condition logs for unsafe and safe stock decrement strategies."

    initial_stock = 1
    worker_count = 2

    def handle(self, *args, **options):
        self.log_id = f"CHECKOUT-RACE-{uuid4().hex[:8].upper()}"
        metrics = []

        self.stdout.write(f"\n1. BEFORE (problem): log_id={self.log_id}-BEFORE")
        self.stdout.write(
            "Scenario: initial_stock=1, parallel_checkouts=2, quantity_per_checkout=1"
        )
        self.stdout.write("Method: UNSAFE_READ_THEN_WRITE")
        metrics.append(self.run_strategy("UNSAFE", self.unsafe_checkout))

        self.stdout.write(f"\n2. AFTER (solution A): log_id={self.log_id}-AFTER-A")
        self.stdout.write(
            "Same scenario -> better result"
        )
        self.stdout.write("Method: ROW_LOCK_SELECT_FOR_UPDATE")
        metrics.append(self.run_strategy("ROW_LOCK", self.row_lock_checkout))

        self.stdout.write(f"\n2. AFTER (solution B): log_id={self.log_id}-AFTER-B")
        self.stdout.write(
            "Same scenario -> better result"
        )
        self.stdout.write("Method: ATOMIC_CONDITIONAL_UPDATE")
        metrics.append(self.run_strategy("CONDITIONAL_UPDATE", self.conditional_update_checkout))

        self.print_comparison(metrics)

    def run_strategy(self, prefix, checkout_func):
        variant, users = self.create_race_data(prefix, stock=self.initial_stock)
        start_barrier = Barrier(self.worker_count)
        if prefix == "UNSAFE":
            self.unsafe_validation_barrier = Barrier(self.worker_count)
        results = []
        errors = []
        started_at = perf_counter()

        def worker(user, label):
            close_old_connections()
            worker_started_at = perf_counter()
            try:
                self.stdout.write(f"[{prefix}][{label}] ready")
                start_barrier.wait(timeout=10)
                order_id = checkout_func(user, label)
                elapsed_ms = self.elapsed_ms(worker_started_at)
                self.stdout.write(f"[{prefix}][{label}] SUCCESS order_id={order_id} duration_ms={elapsed_ms}")
                results.append((label, "SUCCESS", order_id, elapsed_ms))
            except Exception as exc:
                elapsed_ms = self.elapsed_ms(worker_started_at)
                self.stdout.write(f"[{prefix}][{label}] FAILED reason={exc} duration_ms={elapsed_ms}")
                results.append((label, "FAILED", str(exc), elapsed_ms))
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            Thread(target=worker, args=(user, f"T{index}"))
            for index, user in enumerate(users, start=1)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        duration_ms = self.elapsed_ms(started_at)
        metric = self.build_metric(prefix, variant, results, errors, duration_ms)
        self.print_strategy_summary(metric)
        return metric

    @transaction.atomic
    def unsafe_checkout(self, user, label):
        cart = Cart.objects.filter(customer=user, status=CartStatus.ACTIVE).order_by("-created_at").first()
        if not cart:
            raise ValueError("No active cart.")

        item = CartItem.objects.select_related("variant").get(cart=cart)
        inventory = InventoryRecord.objects.get(variant=item.variant)
        available_before_order = inventory.quantity_available
        self.stdout.write(
            f"[UNSAFE][{label}] validation_read stock={available_before_order} requested={item.quantity}"
        )

        if item.quantity > available_before_order:
            raise ValueError(f"Only {available_before_order} available.")

        self.unsafe_validation_barrier.wait(timeout=10)

        order = self.create_order_from_item(user, item, f"Unsafe User {label}")

        inventory.quantity_available = available_before_order - item.quantity
        inventory.save(update_fields=["quantity_available", "updated_at"])
        self.clear_cart(cart)

        self.stdout.write(
            f"[UNSAFE][{label}] stock_write old_read={available_before_order} new_stock={inventory.quantity_available}"
        )
        return order.id

    def row_lock_checkout(self, user, label):
        try:
            order = checkout_cart(
                user,
                customer_name=f"Row Lock User {label}",
                phone_number=user.phone_number,
                shipping_address="Damascus",
                province="Damascus",
            )
        except CheckoutError as exc:
            raise ValueError("Stock was already consumed by another checkout.") from exc
        return order.id

    @transaction.atomic
    def conditional_update_checkout(self, user, label):
        cart = Cart.objects.select_for_update().filter(
            customer=user,
            status=CartStatus.ACTIVE,
        ).order_by("-created_at").first()
        if not cart:
            raise ValueError("No active cart.")

        item = CartItem.objects.select_related("variant").get(cart=cart)
        self.stdout.write(
            f"[CONDITIONAL_UPDATE][{label}] atomic_update requested={item.quantity}"
        )
        updated_rows = InventoryRecord.objects.filter(
            variant=item.variant,
            quantity_available__gte=item.quantity,
        ).update(quantity_available=F("quantity_available") - item.quantity)

        if updated_rows == 0:
            raise ValueError("Stock was already consumed by another checkout.")

        order = self.create_order_from_item(user, item, f"Conditional Update User {label}")
        self.clear_cart(cart)
        return order.id

    def create_order_from_item(self, user, item, customer_name):
        order = Order.objects.create(
            customer=user,
            status=OrderStatus.PENDING,
            total_amount=item.unit_price_snapshot * item.quantity,
            customer_name=customer_name,
            phone_number=user.phone_number,
            shipping_address="Damascus",
            province="Damascus",
        )
        OrderItem.objects.create(
            order=order,
            variant=item.variant,
            quantity=item.quantity,
            unit_price=item.unit_price_snapshot,
        )
        return order

    def clear_cart(self, cart):
        CartItem.objects.filter(cart=cart).delete()
        cart.status = CartStatus.ORDERED
        cart.save(update_fields=["status", "updated_at"])

    def create_race_data(self, prefix, stock):
        run_id = uuid4().hex[:8]
        category = Category.objects.create(name=f"{prefix} Category {run_id}")
        brand = Brand.objects.create(name=f"{prefix} Brand {run_id}")
        product = Product.objects.create(
            name=f"{prefix} Product {run_id}",
            category=category,
            brand=brand,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku=f"{prefix}-{run_id}",
            price=Decimal("10.00"),
            is_active=True,
        )
        InventoryRecord.objects.create(variant=variant, quantity_available=stock)

        users = []
        phone_prefix = prefix.replace("_", "")[:8].lower()
        for index in range(1, self.worker_count + 1):
            user = User(
                phone_number=f"{phone_prefix}{run_id}{index}"[:20],
                first_name=f"{prefix} User {index}",
                user_type=UserType.CUSTOMER,
            )
            user.set_password("password123")
            user.save()
            cart = Cart.objects.create(customer=user, status=CartStatus.ACTIVE)
            CartItem.objects.create(
                cart=cart,
                variant=variant,
                quantity=1,
                unit_price_snapshot=variant.price,
            )
            users.append(user)

        self.stdout.write(
            f"[{prefix}] setup sku={variant.sku} initial_stock={stock} "
            f"parallel_checkouts={self.worker_count} quantity_per_checkout=1"
        )
        return variant, users

    def build_metric(self, prefix, variant, results, errors, duration_ms):
        variant.inventory_record.refresh_from_db()
        order_count = Order.objects.filter(items__variant=variant).distinct().count()
        sold_quantity = sum(
            OrderItem.objects.filter(variant=variant).values_list("quantity", flat=True)
        )
        effective_stock = self.initial_stock - sold_quantity
        oversold_units = max(sold_quantity - self.initial_stock, 0)
        success_count = sum(1 for result in results if result[1] == "SUCCESS")
        failed_count = sum(1 for result in results if result[1] == "FAILED")

        return {
            "prefix": prefix,
            "duration_ms": duration_ms,
            "db_stock": variant.inventory_record.quantity_available,
            "effective_stock": effective_stock,
            "orders": order_count,
            "sold_quantity": sold_quantity,
            "oversold_units": oversold_units,
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": len(errors),
            "results": results,
        }

    def print_strategy_summary(self, metric):
        prefix = metric["prefix"]
        if prefix == "UNSAFE":
            diagnosis = "problem=oversell"
            shows = "This shows: error=oversell, slowdown_or_overload_risk=extra_invalid_orders"
        elif prefix == "ROW_LOCK":
            diagnosis = "solution=serialized_stock_access"
            shows = "This shows: fixed_error=no_oversell, tradeoff=possible_wait_on_locked_stock_row"
        else:
            diagnosis = "solution=single_atomic_stock_update"
            shows = "This shows: fixed_error=no_oversell, tradeoff=fast_failure_when_stock_is_gone"

        self.stdout.write(f"[{prefix}] results={metric['results']}")
        self.stdout.write(
            f"[{prefix}] log_number={self.log_id}-{prefix} duration_ms={metric['duration_ms']} "
            f"stock={metric['effective_stock']} db_stock={metric['db_stock']} "
            f"orders={metric['orders']} sold_quantity={metric['sold_quantity']} "
            f"oversold_units={metric['oversold_units']} successes={metric['success_count']} "
            f"failures={metric['failed_count']} errors={metric['errors']} {diagnosis}"
        )
        self.stdout.write(f"[{prefix}] {shows}")

    def print_comparison(self, metrics):
        by_prefix = {metric["prefix"]: metric for metric in metrics}
        unsafe = by_prefix["UNSAFE"]
        safe_metrics = [by_prefix["ROW_LOCK"], by_prefix["CONDITIONAL_UPDATE"]]
        best = min(safe_metrics, key=lambda metric: metric["duration_ms"])

        self.stdout.write(f"\n3. COMPARISON: log_id={self.log_id}-COMPARISON")
        self.stdout.write("Duration:")
        self.stdout.write(f"Before: {unsafe['duration_ms']}ms")
        for metric in safe_metrics:
            self.stdout.write(f"After ({metric['prefix']}): {metric['duration_ms']}ms")
        self.stdout.write("_______")
        self.stdout.write("Stock:")
        self.stdout.write(f"Before: stock = {unsafe['effective_stock']}")
        for metric in safe_metrics:
            self.stdout.write(f"After ({metric['prefix']}): stock = {metric['effective_stock']}")
        self.stdout.write("_______")
        self.stdout.write("Orders and oversell:")
        self.stdout.write(
            f"Before: orders={unsafe['orders']}, sold_quantity={unsafe['sold_quantity']}, "
            f"oversold_units={unsafe['oversold_units']}"
        )
        for metric in safe_metrics:
            self.stdout.write(
                f"After ({metric['prefix']}): orders={metric['orders']}, "
                f"sold_quantity={metric['sold_quantity']}, oversold_units={metric['oversold_units']}, "
                f"failures={metric['failed_count']}"
            )
        self.stdout.write(
            f"Best measured safe strategy: {best['prefix']} duration_ms={best['duration_ms']}"
        )
        self.stdout.write(
            "Note: compare several runs. Thread scheduling and database load can change timings."
        )

    def elapsed_ms(self, started_at):
        return round((perf_counter() - started_at) * 1000, 2)
