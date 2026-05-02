from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.inventory.models import DailySalesProcessing
from apps.orders.models import Order, OrderStatus
from apps.orders import tasks_batch


class Command(BaseCommand):
    help = (
        "Show a readable summary of daily sales batch processing for a date, "
        "including orders, chunk progress, and final status."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "processing_date",
            type=str,
            help="Date to inspect in YYYY-MM-DD format (e.g., 2026-05-04).",
        )

    def handle(self, *args, **options):
        processing_date_str = options["processing_date"]

        try:
            processing_date = datetime.strptime(processing_date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Invalid date format: {processing_date_str}. Expected YYYY-MM-DD."
            ) from exc

        processing_record = DailySalesProcessing.objects.filter(
            processing_date=processing_date
        ).first()

        pending_orders = Order.objects.filter(
            created_at__date=processing_date,
            status=OrderStatus.PENDING,
        ).count()
        expected_chunks = (
            pending_orders + tasks_batch.CHUNK_SIZE - 1
        ) // tasks_batch.CHUNK_SIZE if pending_orders else 0

        self.stdout.write("=" * 72)
        self.stdout.write("  DAILY SALES PROCESSING STATUS")
        self.stdout.write("=" * 72)
        self.stdout.write(f"Date: {processing_date}")
        self.stdout.write(f"Pending orders: {pending_orders}")
        self.stdout.write(f"Chunk size: {tasks_batch.CHUNK_SIZE}")
        self.stdout.write(f"Expected chunks: {expected_chunks}")

        if not processing_record:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("No processing record found for this date."))
            return

        progress_ratio = (
            processing_record.processed_chunks / processing_record.total_chunks
            if processing_record.total_chunks
            else 0
        )
        progress_percent = int(progress_ratio * 100)

        self.stdout.write("")
        self.stdout.write(f"Status: {processing_record.status.upper()}")
        self.stdout.write(
            f"Progress: {processing_record.processed_chunks}/{processing_record.total_chunks} chunks ({progress_percent}%)"
        )
        self.stdout.write(f"Failed chunks: {processing_record.failed_chunks}")
        self.stdout.write(f"Last processed order ID: {processing_record.last_processed_order_id}")
        self.stdout.write(
            f"Updated at: {processing_record.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if processing_record.status == "completed":
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Batch completed successfully."))
        elif processing_record.status == "in_progress":
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Batch is still running."))
        elif processing_record.status == "failed":
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Batch failed."))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Batch is pending."))
