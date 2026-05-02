from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryRecord
from apps.orders.models import Order, OrderItem, OrderStatus


class Command(BaseCommand):
    help = "Seed demo pending orders for batch-comparison testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "processing_date",
            nargs="?",
            default="2026-05-04",
            help="Date to backdate the demo orders to in YYYY-MM-DD format. Defaults to 2026-05-04.",
        )
        parser.add_argument(
            "--orders",
            type=int,
            default=100,
            help="Number of demo orders to create. Default: 100.",
        )
        parser.add_argument(
            "--items-per-order",
            type=int,
            default=5,
            help="Number of line items per order. Default: 5.",
        )
        parser.add_argument(
            "--inventory-quantity",
            type=int,
            default=1000,
            help="Inventory quantity to set for the demo variant. Default: 1000.",
        )
        parser.add_argument(
            "--tag",
            type=str,
            default="BATCH-DEMO",
            help="Customer name prefix used to identify and clean up demo orders. Default: BATCH-DEMO.",
        )
        parser.add_argument(
            "--variant-sku",
            type=str,
            default="RICE-S",
            help="Variant SKU to attach the demo orders to. Default: RICE-S.",
        )

    def handle(self, *args, **options):
        processing_date_str = options["processing_date"]
        orders_to_create = options["orders"]
        items_per_order = options["items_per_order"]
        inventory_quantity = options["inventory_quantity"]
        tag = options["tag"]
        variant_sku = options["variant_sku"]

        try:
            processing_date = datetime.strptime(processing_date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Invalid date format: {processing_date_str}. Expected YYYY-MM-DD."
            ) from exc

        user = get_user_model().objects.first()
        if not user:
            raise CommandError(
                "No user found. Create one first with python manage.py createsuperuser"
            )

        try:
            variant = ProductVariant.objects.get(sku=variant_sku)
        except ProductVariant.DoesNotExist as exc:
            raise CommandError(
                f"Variant with SKU '{variant_sku}' does not exist. Run python manage.py seed_demo_store first."
            ) from exc

        InventoryRecord.objects.update_or_create(
            variant=variant,
            defaults={
                "quantity_available": inventory_quantity,
                "low_stock_threshold": 50,
            },
        )

        Order.objects.filter(customer_name__startswith=tag).delete()

        processing_dt = timezone.make_aware(datetime.combine(processing_date, time(12, 0, 0)))

        created_orders = 0
        created_items = 0

        for index in range(orders_to_create):
            order = Order.objects.create(
                customer=user,
                status=OrderStatus.PENDING,
                total_amount=Decimal("250.00"),
                customer_name=f"{tag} Customer {index}",
                phone_number="1234567890",
                shipping_address=f"{tag} Address",
                province="Test Province",
            )

            for _ in range(items_per_order):
                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    quantity=1,
                    unit_price=Decimal("50.00"),
                )
                created_items += 1

            Order.objects.filter(id=order.id).update(
                created_at=processing_dt,
                updated_at=processing_dt,
            )
            created_orders += 1

        pending_orders = Order.objects.filter(
            created_at__date=processing_date,
            status=OrderStatus.PENDING,
            customer_name__startswith=tag,
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_orders} pending orders for {processing_date}"
            )
        )
        self.stdout.write(f"Created items: {created_items}")
        self.stdout.write(f"Pending demo orders for {processing_date}: {pending_orders}")
        self.stdout.write(f"Variant SKU: {variant_sku}")
        self.stdout.write(f"Inventory quantity: {inventory_quantity}")
