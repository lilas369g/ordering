"""
Management command to manually trigger daily sales inventory batch processing.

Usage:
    python manage.py process_daily_sales python manage.py process_daily_sales_batch
    python manage.py process_daily_sales_batch 2026-05-01
"""

import logging
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.orders.tasks_batch import process_daily_sales_inventory


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Trigger the daily sales inventory batch processing task. "
        "Optionally specify a date in YYYY-MM-DD format. Defaults to today."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "processing_date",
            nargs="?",
            type=str,
            help="Date to process in YYYY-MM-DD format (e.g., 2026-05-01). Defaults to today.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            help="Run as async Celery task (returns immediately). Default is sync.",
        )
        parser.add_argument(
            "--eager",
            action="store_true",
            help="Force synchronous execution regardless of CELERY_TASK_ALWAYS_EAGER setting.",
        )

    def handle(self, *args, **options):
        processing_date = options.get("processing_date")

        # Validate date format if provided
        if processing_date:
            try:
                datetime.strptime(processing_date, "%Y-%m-%d")
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Date format valid: {processing_date}")
                )
            except ValueError:
                raise CommandError(
                    f"Invalid date format: {processing_date}. "
                    f"Expected YYYY-MM-DD (e.g., 2026-05-01)"
                )

        # Determine execution mode
        async_mode = options.get("async", False)
        eager_mode = options.get("eager", False)

        self.stdout.write(
            self.style.WARNING(
                "\n" + "=" * 70
            )
        )
        self.stdout.write(
            self.style.WARNING("  DAILY SALES INVENTORY BATCH PROCESSING")
        )
        self.stdout.write(
            self.style.WARNING("=" * 70)
        )

        self.stdout.write("\n📋 Configuration:")
        self.stdout.write(
            f"   Processing Date: {processing_date or 'Today (auto-detected)'}"
        )
        self.stdout.write(f"   Execution Mode: {'Async (Celery Queue)' if async_mode else 'Sync (Immediate)'}")

        if eager_mode:
            self.stdout.write(
                self.style.WARNING(
                    "   ⚠ Forced eager execution (synchronous, for testing)"
                )
            )

        self.stdout.write("\n📊 What this command does:")
        self.stdout.write("   1. EXTRACT: Query all PENDING orders from the date")
        self.stdout.write("   2. SPLIT: Divide into chunks of 500 records")
        self.stdout.write("   3. TRANSFORM: Calculate inventory deductions per variant")
        self.stdout.write("   4. LOAD: Bulk update inventory records")
        self.stdout.write("   5. CHECKPOINT: Track progress for crash recovery")
        self.stdout.write("   6. PARTIAL FAILURE: Continue on chunk errors")

        self.stdout.write("\n🚀 Triggering task...")

        try:
            if async_mode and not eager_mode:
                # Queue the task (returns immediately)
                self.stdout.write(
                    self.style.HTTP_INFO("   Queuing task to Celery broker...")
                )
                result = process_daily_sales_inventory.delay(processing_date)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Task queued successfully!\n"
                        f"   Task ID: {result.id}\n"
                        f"   Status: PENDING\n"
                        f"   Check Celery worker logs for real-time progress."
                    )
                )
                return

            else:
                # Run synchronously (wait for completion)
                if eager_mode:
                    self.stdout.write(
                        self.style.HTTP_INFO(
                            "   Running in forced eager mode (synchronous)..."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.HTTP_INFO("   Running synchronously (waiting)...")
                    )

                result = process_daily_sales_inventory(processing_date)

                # Display results
                self.stdout.write(
                    self.style.SUCCESS(
                        "\n" + "=" * 70
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS("  ✓ BATCH PROCESSING COMPLETED")
                )
                self.stdout.write(
                    self.style.SUCCESS("=" * 70)
                )

                self.stdout.write(f"\n📊 Results:")
                self.stdout.write(f"   Status: {result.get('status', 'unknown').upper()}")
                self.stdout.write(
                    f"   Processing Date: {result.get('processing_date', 'N/A')}"
                )
                self.stdout.write(
                    f"   Total Orders: {result.get('total_orders', 0)}"
                )
                self.stdout.write(f"   Total Chunks: {result.get('total_chunks', 0)}")
                self.stdout.write(
                    f"   Successfully Processed: {result.get('processed_chunks', 0)}"
                )
                self.stdout.write(
                    f"   Failed Chunks: {result.get('failed_chunks', 0)}"
                )

                if result.get("failed_chunks", 0) > 0:
                    self.stdout.write(
                        self.style.ERROR(f"\n⚠ Failed chunks details:")
                    )
                    for failed_chunk in result.get("failed_chunk_details", []):
                        self.stdout.write(
                            self.style.ERROR(
                                f"   - Chunk {failed_chunk['chunk_num']}: "
                                f"{failed_chunk['error']}"
                            )
                        )

                self.stdout.write("\n✅ Batch processing task completed.\n")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"\n✗ Error triggering batch processing task: {str(e)}"
                )
            )
            logger.exception("Error in process_daily_sales_batch command")
            raise CommandError(str(e))
