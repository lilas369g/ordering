from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Sum

from apps.inventory.models import (
    DailySalesProcessing,
    InventoryRecord,
    StockMovement,
    StockMovementType,
)


class Command(BaseCommand):
    help = (
        "Reset a daily sales processing run for a specific date by restoring "
        "inventory, deleting daily-processing stock movements, and removing "
        "the processing record so the date can be rerun intentionally."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "processing_date",
            type=str,
            help="Date to reset in YYYY-MM-DD format (e.g., 2026-05-04).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be reset without changing any data.",
        )

    def handle(self, *args, **options):
        processing_date_str = options["processing_date"]
        dry_run = options["dry_run"]

        try:
            processing_date = datetime.strptime(processing_date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Invalid date format: {processing_date_str}. Expected YYYY-MM-DD."
            ) from exc

        processing_record = DailySalesProcessing.objects.filter(
            processing_date=processing_date
        ).first()

        movement_qs = StockMovement.objects.filter(
            movement_type=StockMovementType.DAILY_PROCESSING,
            note__startswith=f"Daily sales processing for {processing_date}",
        )
        movement_rollup = list(
            movement_qs.values("variant_id", "variant__sku")
            .annotate(total_quantity=Sum("quantity"), movement_count=Count("id"))
            .order_by("variant__sku")
        )

        if not processing_record and not movement_rollup:
            raise CommandError(
                f"Nothing to reset for {processing_date}. No processing record and no daily-processing stock movements were found."
            )

        restored_rows = []
        for row in movement_rollup:
            total_quantity = row["total_quantity"] or 0
            restored_units = -total_quantity
            if restored_units < 0:
                raise CommandError(
                    f"Unexpected positive quantity found in daily-processing movements for variant {row['variant__sku']}."
                )
            restored_rows.append(
                {
                    "variant_id": row["variant_id"],
                    "sku": row["variant__sku"],
                    "restored_units": restored_units,
                    "movement_count": row["movement_count"],
                }
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry run for {processing_date}")
            )
            self.stdout.write(f"Processing record exists: {bool(processing_record)}")
            self.stdout.write(f"Daily-processing stock movements: {movement_qs.count()}")
            self.stdout.write(f"Affected variants: {len(restored_rows)}")
            for row in restored_rows:
                self.stdout.write(
                    f"- {row['sku']}: restore {row['restored_units']} units from {row['movement_count']} movement(s)"
                )
            self.stdout.write("No data was changed.")
            return

        with transaction.atomic():
            for row in restored_rows:
                try:
                    inventory = InventoryRecord.objects.select_for_update().get(
                        variant_id=row["variant_id"]
                    )
                except InventoryRecord.DoesNotExist as exc:
                    raise CommandError(
                        f"Missing inventory record for variant {row['sku']}. Cannot restore this date safely."
                    ) from exc

                inventory.quantity_available = (
                    inventory.quantity_available + row["restored_units"]
                )
                inventory.save(update_fields=["quantity_available"])

            deleted_movements, _ = movement_qs.delete()

            if processing_record:
                processing_record.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Reset completed for {processing_date}."
            )
        )
        self.stdout.write(f"Restored variants: {len(restored_rows)}")
        self.stdout.write(f"Deleted daily-processing stock movements: {deleted_movements}")
        self.stdout.write(
            "Deleted processing record: yes" if processing_record else "Deleted processing record: no record found"
        )
        self.stdout.write(
            "You can now rerun the same date intentionally with --compare or --async."
        )
