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

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose-steps",
            action="store_true",
            help="Print low-level worker and stock operation logs.",
        )

    def handle(self, *args, **options):
        self.log_id = f"CHECKOUT-RACE-{uuid4().hex[:8].upper()}"
        self.verbose_steps = options["verbose_steps"]
        metrics = []

        self.print_main_header()
        metrics.append(self.run_strategy("UNSAFE", self.unsafe_checkout))
        metrics.append(self.run_strategy("ROW_LOCK", self.row_lock_checkout))
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
                if getattr(self, "verbose_steps", False):
                    self.stdout.write(f"[{prefix}][{label}] ready")
                start_barrier.wait(timeout=10)
                order_id = checkout_func(user, label)
                elapsed_ms = self.elapsed_ms(worker_started_at)
                results.append((label, "SUCCESS", order_id, elapsed_ms))
            except Exception as exc:
                elapsed_ms = self.elapsed_ms(worker_started_at)
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
        self.print_strategy_report(metric)
        return metric

    @transaction.atomic
    def unsafe_checkout(self, user, label):
        cart = Cart.objects.filter(customer=user, status=CartStatus.ACTIVE).order_by("-created_at").first()
        if not cart:
            raise ValueError("No active cart.")

        item = CartItem.objects.select_related("variant").get(cart=cart)
        inventory = InventoryRecord.objects.get(variant=item.variant)
        available_before_order = inventory.quantity_available
        if getattr(self, "verbose_steps", False):
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

        if getattr(self, "verbose_steps", False):
            self.stdout.write(
                f"[UNSAFE][{label}] stock_write old_read={available_before_order} "
                f"new_stock={inventory.quantity_available}"
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
        if getattr(self, "verbose_steps", False):
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

        if getattr(self, "verbose_steps", False):
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

    def print_main_header(self):
        self.stdout.write("\n============================================================")
        self.stdout.write("Checkout Race Condition Demo")
        self.stdout.write("============================================================")
        self.stdout.write("\nScenario:")
        self.stdout.write(f"- initial_stock: {self.initial_stock}")
        self.stdout.write(f"- parallel_checkouts: {self.worker_count}")
        self.stdout.write("- quantity_per_checkout: 1")

    def print_strategy_report(self, metric):
        prefix = metric["prefix"]
        self.stdout.write("\n============================================================")
        self.stdout.write(f"{self.strategy_title(prefix)}: log_id={self.strategy_log_id(prefix)}")
        self.stdout.write("============================================================")
        self.stdout.write(f"Method: {self.strategy_method(prefix)}")
        self.stdout.write("\nMeaning:")
        self.stdout.write(self.strategy_meaning(prefix))
        self.stdout.write("\nWorker results:")
        self.print_worker_results(metric)
        self.stdout.write("\nSummary:")
        self.stdout.write(f"- status: {self.strategy_status(metric)}")
        self.stdout.write(f"- duration_ms: {metric['duration_ms']}")
        self.stdout.write(f"- db_stock: {metric['db_stock']}")
        self.stdout.write(f"- effective_stock: {metric['effective_stock']}")
        self.stdout.write(f"- orders: {metric['orders']}")
        self.stdout.write(f"- sold_quantity: {metric['sold_quantity']}")
        self.stdout.write(f"- oversold_units: {metric['oversold_units']}")
        self.stdout.write(f"- successes: {metric['success_count']}")
        self.stdout.write(f"- failures: {metric['failed_count']}")
        self.stdout.write("\nThis shows:")
        for line in self.strategy_explanation(prefix):
            self.stdout.write(line)

    def strategy_title(self, prefix):
        titles = {
            "UNSAFE": "1. BEFORE (problem)",
            "ROW_LOCK": "2. AFTER (solution A): same scenario ---> better result",
            "CONDITIONAL_UPDATE": "2. AFTER (solution B): same scenario ---> better result",
        }
        return titles[prefix]

    def strategy_log_id(self, prefix):
        suffixes = {
            "UNSAFE": "BEFORE",
            "ROW_LOCK": "AFTER-A",
            "CONDITIONAL_UPDATE": "AFTER-B",
        }
        return f"{self.log_id}-{suffixes[prefix]}"

    def strategy_method(self, prefix):
        methods = {
            "UNSAFE": "UNSAFE_READ_THEN_WRITE",
            "ROW_LOCK": "ROW_LOCK_SELECT_FOR_UPDATE",
            "CONDITIONAL_UPDATE": "ATOMIC_CONDITIONAL_UPDATE",
        }
        return methods[prefix]

    def strategy_meaning(self, prefix):
        meanings = {
            "UNSAFE": (
                "Two users read the same stock before either checkout writes the new stock.\n"
                "This can create more successful orders than the available stock."
            ),
            "ROW_LOCK": (
                "The stock row is locked during checkout, so only one checkout can safely "
                "consume the stock first."
            ),
            "CONDITIONAL_UPDATE": (
                "The stock decrement happens as one atomic conditional update.\n"
                "If stock is already gone, the update affects 0 rows and checkout fails safely."
            ),
        }
        return meanings[prefix]

    def strategy_status(self, metric):
        if metric["prefix"] == "UNSAFE" and metric["oversold_units"] > 0:
            return "PROBLEM_OVERSOLD"
        if metric["oversold_units"] == 0:
            return "SAFE_NO_OVERSELL"
        return "CHECK_RESULT"

    def print_worker_results(self, metric):
        for label, status, value, duration_ms in sorted(metric["results"]):
            if status == "SUCCESS":
                self.stdout.write(f"- {label}: SUCCESS order_id={value} duration_ms={duration_ms}")
            else:
                self.stdout.write(f"- {label}: FAILED reason={value} duration_ms={duration_ms}")

    def strategy_explanation(self, prefix):
        explanations = {
            "UNSAFE": [
                (
                    "This shows: oversell happened because stock validation and stock update "
                    "were not protected as one safe operation."
                ),
                (
                    "Invalid extra orders also create unnecessary downstream work, which can "
                    "cause overload or slowdown risk."
                ),
            ],
            "ROW_LOCK": [
                (
                    "No oversell occurs. The second checkout fails safely after the stock "
                    "has already been consumed."
                ),
                "This shows: stock access was serialized using row locking.",
            ],
            "CONDITIONAL_UPDATE": [
                (
                    "No oversell occurs. The stock update is protected as a single atomic "
                    "database operation."
                ),
                "This shows: the conditional update prevents invalid stock decrement.",
            ],
        }
        return explanations[prefix]

    def print_comparison(self, metrics):
        by_prefix = {metric["prefix"]: metric for metric in metrics}
        unsafe = by_prefix["UNSAFE"]
        row_lock = by_prefix["ROW_LOCK"]
        conditional_update = by_prefix["CONDITIONAL_UPDATE"]

        self.stdout.write("\n============================================================")
        self.stdout.write("3. COMPARISON")
        self.stdout.write("============================================================")
        self.stdout.write("\nCorrectness:")
        self.print_correctness_comparison("Before UNSAFE", unsafe)
        self.print_correctness_comparison("After ROW_LOCK", row_lock)
        self.print_correctness_comparison("After CONDITIONAL_UPDATE", conditional_update)

        self.stdout.write("\nDuration:")
        self.stdout.write(f"    Before: {unsafe['duration_ms']}ms")
        self.stdout.write(f"    After ROW_LOCK: {row_lock['duration_ms']}ms")
        self.stdout.write(f"    After CONDITIONAL_UPDATE: {conditional_update['duration_ms']}ms")


    def print_correctness_comparison(self, title, metric):
        self.stdout.write(f"\n{title}:")
        self.stdout.write(f"- stock = {metric['effective_stock']}")
        self.stdout.write(f"- orders = {metric['orders']}")
        self.stdout.write(f"- sold_quantity = {metric['sold_quantity']}")
        self.stdout.write(f"- oversold_units = {metric['oversold_units']}")

    def elapsed_ms(self, started_at):
        return round((perf_counter() - started_at) * 1000, 2)
