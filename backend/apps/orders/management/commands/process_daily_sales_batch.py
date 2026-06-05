"""
Management command to manually trigger daily sales inventory batch processing.

Usage:
    python manage.py process_daily_sales_batch
    python manage.py process_daily_sales_batch 2026-05-01
    python manage.py process_daily_sales_batch 2026-05-01 --compare
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

# Project root (…/ordering) — where benchmark result JSON files are written.
PROJECT_ROOT = Path(__file__).resolve().parents[5]
BATCH_RESULTS_PATH = PROJECT_ROOT / "batch_etl_results.json"

from apps.inventory.models import DailySalesProcessing
from apps.orders.models import Order, OrderStatus
from apps.orders.tasks_batch import (
    CHUNK_SIZE,
    benchmark_realtime_daily_sales_inventory,
    process_daily_sales_inventory_parallel,
    process_daily_sales_inventory,
)


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
            "--compare",
            action="store_true",
            help="Run a real-time benchmark first, then run the batch ETL and print a BEFORE/AFTER/COMPARISON report.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            help="Run as async Celery fan-out (dispatches chunk tasks and returns immediately). Default is sync.",
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

        processing_date_value = (
            datetime.strptime(processing_date, "%Y-%m-%d").date()
            if processing_date
            else datetime.now().date()
        )

        compare_mode = options.get("compare", False)
        async_mode = options.get("async", False)
        eager_mode = options.get("eager", False)

        if compare_mode and async_mode:
            raise CommandError("--compare cannot be used with --async. Use sync mode for the benchmark.")

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
        self.stdout.write(
            f"   Execution Mode: {'Async (Celery Parallel Fan-out)' if async_mode else 'Sync (Immediate)'}"
        )

        if compare_mode:
            self.stdout.write("   Comparison Mode: Real-time BEFORE vs Batch AFTER")

        if eager_mode:
            self.stdout.write(
                self.style.WARNING(
                    "   ⚠ Forced eager execution (synchronous, for testing)"
                )
            )

        self.stdout.write("\n📊 What this command does:")
        self.stdout.write("   1. EXTRACT: Query all PENDING orders from the date")
        self.stdout.write("   2. SPLIT: Divide into 500-order chunks")
        self.stdout.write("   3. FAN-OUT: Dispatch one Celery task per chunk in async mode")
        self.stdout.write("   4. TRANSFORM: Calculate inventory deductions per variant")
        self.stdout.write("   5. LOAD: Bulk update inventory records")
        self.stdout.write("   6. CHECKPOINT: Track progress for crash recovery")
        self.stdout.write("   7. PARTIAL FAILURE: Continue on chunk errors")

        self.stdout.write("\n🚀 Triggering task...")

        try:
            if compare_mode:
                if DailySalesProcessing.objects.filter(processing_date=processing_date_value).exists():
                    raise CommandError(
                        f"Processing date {processing_date} already has a processing record. Use a fresh date with pending orders for comparison."
                    )

                pending_orders = Order.objects.filter(
                    created_at__date=processing_date_value,
                    status=OrderStatus.PENDING,
                ).count()
                if pending_orders == 0:
                    raise CommandError(
                        f"No pending orders found for {processing_date}. Create a fresh test dataset first so the comparison is meaningful."
                    )

                self.stdout.write(
                    self.style.HTTP_INFO("   Running real-time benchmark (dry-run)...")
                )
                realtime_result = benchmark_realtime_daily_sales_inventory(processing_date)

                self.stdout.write(
                    self.style.HTTP_INFO("   Running batch ETL (real save)...")
                )
                batch_result = process_daily_sales_inventory(processing_date)

                batch_report = batch_result.get("comparison_report", {})
                batch_before = batch_report.get("before", {})
                batch_after = batch_report.get("after", {})
                batch_comparison = batch_report.get("comparison", {})

                self.stdout.write(
                    self.style.SUCCESS("\n" + "=" * 70)
                )
                self.stdout.write(
                    self.style.SUCCESS("  ✓ REAL-TIME VS BATCH COMPARISON")
                )
                self.stdout.write(
                    self.style.SUCCESS("=" * 70)
                )

                self.stdout.write("\n1. BEFORE (المشكلة) - Real-Time Processing")
                self.stdout.write(f"   Status: {realtime_result.get('status', 'unknown').upper()}")
                self.stdout.write(f"   Total Orders: {realtime_result.get('total_orders', 0)}")
                self.stdout.write(f"   Orders Processed: {realtime_result.get('orders_processed', 0)}")
                self.stdout.write(f"   Items Processed: {realtime_result.get('items_processed', 0)}")
                self.stdout.write(
                    f"   Inventory Before: {realtime_result.get('inventory_total_before', 0)}"
                )
                self.stdout.write(
                    f"   Inventory After: {realtime_result.get('inventory_total_after', 0)}"
                )
                self.stdout.write(
                    f"   Inventory Delta: {realtime_result.get('inventory_delta', 0)}"
                )
                self.stdout.write(
                    f"   Stock Movements: {realtime_result.get('stock_movements_created', 0)}"
                )
                self.stdout.write(
                    f"   Processing Time: {realtime_result.get('processing_time_ms', 0)} ms"
                )

                if realtime_result.get("variant_changes"):
                    self.stdout.write("   Variant Changes:")
                    for change in realtime_result.get("variant_changes", [])[:5]:
                        self.stdout.write(
                            f"   - {change['sku']}: {change['before']} -> {change['after']} (Δ {change['delta']})"
                        )

                self.stdout.write("\n2. AFTER (الحل) - Batch ETL")
                self.stdout.write(f"   Status: {batch_result.get('status', 'unknown').upper()}")
                self.stdout.write(f"   Total Orders: {batch_result.get('total_orders', 0)}")
                self.stdout.write(f"   Total Chunks: {batch_result.get('total_chunks', 0)}")
                self.stdout.write(
                    f"   Successfully Processed: {batch_result.get('processed_chunks', 0)}"
                )
                self.stdout.write(f"   Failed Chunks: {batch_result.get('failed_chunks', 0)}")
                self.stdout.write(
                    f"   Inventory Before: {batch_before.get('affected_inventory_total', 0)}"
                )
                self.stdout.write(
                    f"   Inventory After: {batch_after.get('affected_inventory_total', 0)}"
                )
                self.stdout.write(
                    f"   Inventory Delta: {batch_comparison.get('inventory_delta', 0)}"
                )
                self.stdout.write(
                    f"   Stock Movements: {batch_after.get('stock_movements', 0)}"
                )
                self.stdout.write(
                    f"   Processing Time: {batch_comparison.get('processing_time_ms', 0)} ms"
                )

                self.stdout.write("\n3. COMPARISON:")
                realtime_time = realtime_result.get('processing_time_ms', 0)
                batch_time = batch_comparison.get('processing_time_ms', 0)
                time_saved = realtime_time - batch_time
                speedup = round(realtime_time / batch_time, 2) if batch_time else None

                self.stdout.write(f"   Before (Real-Time): {realtime_time} ms")
                self.stdout.write(f"   After (Batch): {batch_time} ms")
                self.stdout.write(f"   Time Saved: {time_saved} ms")
                if speedup is not None:
                    self.stdout.write(f"   Speedup: {speedup}x")

                self.stdout.write(
                    f"   Inventory Delta Match: {realtime_result.get('inventory_delta', 0) == batch_comparison.get('inventory_delta', 0)}"
                )
                self.stdout.write(
                    f"   Stock Movements Match: {realtime_result.get('stock_movements_created', 0) == batch_after.get('stock_movements', 0)}"
                )

                self.save_compare_json(
                    processing_date_value=processing_date_value,
                    realtime_result=realtime_result,
                    batch_result=batch_result,
                    batch_after=batch_after,
                    batch_comparison=batch_comparison,
                    realtime_time=realtime_time,
                    batch_time=batch_time,
                    time_saved=time_saved,
                    speedup=speedup,
                )

                self.stdout.write("\n✅ Comparison completed successfully.\n")
                return

            if async_mode and not eager_mode:
                self.stdout.write(
                    self.style.HTTP_INFO("   Running real-time benchmark (dry-run)...")
                )
                realtime_result = benchmark_realtime_daily_sales_inventory(processing_date)

                pending_orders = Order.objects.filter(
                    created_at__date=processing_date_value,
                    status=OrderStatus.PENDING,
                ).count()
                expected_chunks = (
                    (pending_orders + CHUNK_SIZE - 1) // CHUNK_SIZE
                    if pending_orders
                    else 0
                )

                # Queue the task (returns immediately)
                self.stdout.write(
                    self.style.HTTP_INFO(
                        "   Queuing parallel fan-out task to Celery broker..."
                    )
                )
                async_start = datetime.now()
                result = process_daily_sales_inventory_parallel.delay(
                    processing_date_value.isoformat()
                )
                async_queue_time_ms = int(
                    (datetime.now() - async_start).total_seconds() * 1000
                )

                self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
                self.stdout.write(self.style.SUCCESS("  ✓ REAL-TIME VS BATCH QUEUED"))
                self.stdout.write(self.style.SUCCESS("=" * 70))

                self.stdout.write("\n1. BEFORE (المشكلة) - Real-Time Processing")
                self.stdout.write(
                    f"   Total Orders: {realtime_result.get('total_orders', 0)}"
                )
                self.stdout.write(
                    f"   Orders Processed: {realtime_result.get('orders_processed', 0)}"
                )
                self.stdout.write(
                    f"   Items Processed: {realtime_result.get('items_processed', 0)}"
                )
                self.stdout.write(
                    f"   Inventory Delta: {realtime_result.get('inventory_delta', 0)}"
                )
                self.stdout.write(
                    f"   Stock Movements: {realtime_result.get('stock_movements_created', 0)}"
                )
                self.stdout.write(
                    f"   Processing Time: {realtime_result.get('processing_time_ms', 0)} ms"
                )

                self.stdout.write("\n2. AFTER (الحل) - Batch Queued for Celery")
                self.stdout.write(f"   Total Orders: {pending_orders}")
                self.stdout.write(f"   Chunk Size: {CHUNK_SIZE}")
                self.stdout.write(f"   Expected Chunks: {expected_chunks}")
                self.stdout.write(f"   Queue Status: PENDING")
                self.stdout.write(
                    f"   Celery Workers Waiting: 3 workers can consume the chunks"
                )
                self.stdout.write(
                    f"   Task ID: {result.id}"
                )
                self.stdout.write(
                    f"   Queue Time: {async_queue_time_ms} ms"
                )

                self.stdout.write("\n3. COMPARISON:")
                realtime_time = realtime_result.get('processing_time_ms', 0)
                self.stdout.write(f"   Before: {realtime_time} ms")
                self.stdout.write(f"   After:  {async_queue_time_ms} ms (queue only)")
                self.stdout.write(
                    f"   Time Saved Right Now: {realtime_time - async_queue_time_ms} ms"
                )
                self.stdout.write(
                    f"   Chunks Waiting For Consumers: {expected_chunks}"
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        "\n✓ Task queued successfully!\n"
                        f"   Check Celery worker logs for CHUNK 1/{expected_chunks if expected_chunks else '?'} ..."
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
                status = result.get('status', 'unknown')
                self.stdout.write(f"   Status: {status.upper()}")
                self.stdout.write(
                    f"   Processing Date: {result.get('processing_date', 'N/A')}"
                )

                if status == 'skipped':
                    self.stdout.write(
                        f"   Reason: {result.get('reason', 'Already processed')}"
                    )
                    self.stdout.write("   Total Orders: N/A (already processed)")
                    self.stdout.write("   Total Chunks: 0")
                    self.stdout.write("   Successfully Processed: 0")
                    self.stdout.write("   Failed Chunks: 0")
                    self.stdout.write("\n✅ Batch processing task completed.\n")
                    return

                comparison_report = result.get("comparison_report", {})
                if comparison_report:
                    before = comparison_report.get("before", {})
                    after = comparison_report.get("after", {})
                    comparison = comparison_report.get("comparison", {})
                    variant_changes = comparison_report.get("variant_changes", [])

                    self.stdout.write("\n1. BEFORE (المشكلة):")
                    self.stdout.write(
                        f"   Status: {before.get('status', 'N/A')}"
                    )
                    self.stdout.write(
                        f"   Inventory total: {before.get('affected_inventory_total', 0)}"
                    )
                    self.stdout.write(
                        f"   Stock movements today: {before.get('stock_movements', 0)}"
                    )

                    self.stdout.write("\n2. AFTER (الحل):")
                    self.stdout.write(
                        f"   Status: {after.get('status', 'N/A')}"
                    )
                    self.stdout.write(
                        f"   Inventory total: {after.get('affected_inventory_total', 0)}"
                    )
                    self.stdout.write(
                        f"   Stock movements today: {after.get('stock_movements', 0)}"
                    )

                    self.stdout.write("\n3. COMPARISON:")
                    self.stdout.write(
                        f"   Inventory delta: {comparison.get('inventory_delta', 0)}"
                    )
                    self.stdout.write(
                        f"   Stock movements created: {comparison.get('stock_movements_created', 0)}"
                    )
                    self.stdout.write(
                        f"   Processing time: {comparison.get('processing_time_ms', 0)} ms"
                    )

                    if variant_changes:
                        self.stdout.write("   Variant changes:")
                        for change in variant_changes[:5]:
                            self.stdout.write(
                                f"   - {change['sku']}: {change['before']} -> {change['after']} (Δ {change['delta']})"
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

    def save_compare_json(
        self,
        processing_date_value,
        realtime_result,
        batch_result,
        batch_after,
        batch_comparison,
        realtime_time,
        batch_time,
        time_saved,
        speedup,
    ):
        realtime_delta = realtime_result.get("inventory_delta", 0)
        batch_delta = batch_comparison.get("inventory_delta", 0)
        realtime_movements = realtime_result.get("stock_movements_created", 0)
        batch_movements = batch_after.get("stock_movements", 0)

        output = {
            "last_updated": datetime.now().isoformat(),
            "processing_date": processing_date_value.isoformat(),
            "total_orders": realtime_result.get("total_orders", 0),
            "total_items": realtime_result.get("items_processed", 0),
            "realtime": {
                "label": "Real-Time Processing",
                "processing_time_ms": realtime_time,
                "status": "COMPLETED",
                "orders_processed": realtime_result.get("orders_processed", 0),
                "inventory_delta": realtime_delta,
                "stock_movements": realtime_movements,
            },
            "batch": {
                "label": "Batch ETL",
                "processing_time_ms": batch_time,
                "status": "COMPLETED",
                "chunks_successful": batch_result.get("processed_chunks", 0),
                "chunks_failed": batch_result.get("failed_chunks", 0),
                "inventory_delta": batch_delta,
                "stock_movements": batch_movements,
            },
            "comparison": {
                "time_saved_ms": time_saved,
                "speedup": speedup if speedup is not None else 0,
                "inventory_match": realtime_delta == batch_delta,
                "stock_movements_match": realtime_movements == batch_movements,
            },
        }

        with open(BATCH_RESULTS_PATH, "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2, ensure_ascii=False)
        self.stdout.write(f"Results saved to {BATCH_RESULTS_PATH}")
