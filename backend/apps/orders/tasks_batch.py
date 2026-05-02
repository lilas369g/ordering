"""
Batch Processing Tasks: Daily Sales Inventory Processing
========================================================

This module implements a Celery task for batch processing daily sales inventory
using the ETL (Extract, Transform, Load) pipeline pattern with fixed-size chunking.

Architecture:
- Fixed-Size Chunking: Process 500 orders per chunk
- Parallel Fan-out: Dispatch one Celery task per chunk in async mode
- Extract: Query orders from database
- Transform: Calculate inventory metrics
- Load: Bulk update database efficiently
- Idempotency: Track processed dates to prevent duplicates
- Checkpointing: Log progress to resume if worker crashes
- Partial Failure: Catch errors per chunk, continue processing
"""

import json
import logging
from datetime import datetime

from celery import group, shared_task
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from apps.inventory.models import (
    DailySalesProcessing,
    InventoryRecord,
    ProcessingStatus,
    StockMovement,
    StockMovementType,
)
from apps.orders.models import Order, OrderItem, OrderStatus


logger = logging.getLogger(__name__)

import os
import socket
# Configuration: Number of records per chunk and bulk write batch size
CHUNK_SIZE = 500
BULK_BATCH_SIZE = CHUNK_SIZE


def _parse_processing_date(processing_date_str=None):
    if processing_date_str:
        try:
            return datetime.strptime(processing_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(
                f"[tasks_batch] Invalid date format: {processing_date_str}"
            )
            raise

    return datetime.now().date()


def _get_pending_orders_queryset(processing_date):
    return Order.objects.filter(
        created_at__date=processing_date,
        status=OrderStatus.PENDING,
    ).order_by("id")


def _split_order_ids(order_ids):
    return [
        order_ids[index:index + CHUNK_SIZE]
        for index in range(0, len(order_ids), CHUNK_SIZE)
    ]


def _mark_parallel_chunk_success(processing_record_id, chunk_last_order_id):
    DailySalesProcessing.objects.filter(pk=processing_record_id).update(
        processed_chunks=F("processed_chunks") + 1,
        last_processed_order_id=Greatest(
            F("last_processed_order_id"), Value(chunk_last_order_id)
        ),
        updated_at=timezone.now(),
    )


def _append_parallel_chunk_failure(
    processing_record_id, chunk_num, error_message, chunk_order_ids
):
    failure_entry = {
        "chunk_num": chunk_num,
        "error": error_message,
        "order_range": (
            f"{chunk_order_ids[0]}-{chunk_order_ids[-1]}"
            if chunk_order_ids
            else "unknown"
        ),
    }

    with transaction.atomic():
        processing_record = DailySalesProcessing.objects.select_for_update().get(
            pk=processing_record_id
        )

        existing_errors = []
        if processing_record.error_log:
            try:
                existing_errors = json.loads(processing_record.error_log)
            except json.JSONDecodeError:
                existing_errors = [
                    {"raw_error_log": processing_record.error_log}
                ]

        existing_errors.append(failure_entry)
        processing_record.failed_chunks += 1
        processing_record.error_log = json.dumps(existing_errors, indent=2)
        processing_record.save(
            update_fields=["failed_chunks", "error_log", "updated_at"]
        )


def benchmark_realtime_daily_sales_inventory(processing_date_str=None):
    """Simulate a naive real-time processor and roll back the DB changes.

    This is used for benchmarking only. It updates inventory and creates stock
    movements one row at a time, then rolls the transaction back so the batch
    processor can run on the same dataset afterwards.
    """

    if processing_date_str:
        try:
            processing_date = datetime.strptime(processing_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(
                f"[benchmark_realtime_daily_sales_inventory] Invalid date format: {processing_date_str}"
            )
            raise
    else:
        processing_date = datetime.now().date()

    logger.info(
        f"[benchmark_realtime_daily_sales_inventory] Starting real-time benchmark for date: {processing_date}"
    )

    benchmark_started_at = datetime.now()

    orders_queryset = Order.objects.filter(
        created_at__date=processing_date,
        status=OrderStatus.PENDING,
    ).order_by("id")

    total_orders = orders_queryset.count()
    before_inventory_snapshot = {}
    after_inventory_snapshot = {}
    stock_movements_created = 0
    orders_processed = 0
    items_processed = 0
    missing_inventory_variants = 0

    with transaction.atomic():
        for order in orders_queryset:
            order_items = list(
                OrderItem.objects.filter(order_id=order.id)
                .select_related("variant")
                .order_by("id")
            )

            if not order_items:
                continue

            orders_processed += 1

            for item in order_items:
                try:
                    inventory = InventoryRecord.objects.select_for_update().get(
                        variant_id=item.variant_id
                    )
                except InventoryRecord.DoesNotExist:
                    missing_inventory_variants += 1
                    logger.warning(
                        f"[benchmark_realtime_daily_sales_inventory] No inventory record found for variant {item.variant_id}. Skipping."
                    )
                    continue

                if item.variant_id not in before_inventory_snapshot:
                    before_inventory_snapshot[item.variant_id] = {
                        "sku": inventory.variant.sku,
                        "quantity_available": inventory.quantity_available,
                    }

                inventory.quantity_available = inventory.quantity_available - item.quantity
                inventory.save(update_fields=["quantity_available"])

                after_inventory_snapshot[item.variant_id] = {
                    "sku": inventory.variant.sku,
                    "quantity_available": inventory.quantity_available,
                }

                StockMovement.objects.create(
                    variant_id=item.variant_id,
                    movement_type=StockMovementType.DAILY_PROCESSING,
                    quantity=-item.quantity,
                    note=f"Real-time benchmark for {processing_date} (Order #{item.order_id})",
                )

                stock_movements_created += 1
                items_processed += 1

        transaction.set_rollback(True)

    benchmark_finished_at = datetime.now()
    before_inventory_total = sum(
        item["quantity_available"] for item in before_inventory_snapshot.values()
    )
    after_inventory_total = sum(
        item["quantity_available"] for item in after_inventory_snapshot.values()
    )

    variant_changes = []
    for variant_id, before_snapshot in before_inventory_snapshot.items():
        after_snapshot = after_inventory_snapshot.get(variant_id, before_snapshot)
        variant_changes.append(
            {
                "sku": before_snapshot["sku"],
                "before": before_snapshot["quantity_available"],
                "after": after_snapshot["quantity_available"],
                "delta": after_snapshot["quantity_available"] - before_snapshot["quantity_available"],
            }
        )

    variant_changes.sort(key=lambda item: item["sku"])

    logger.info(
        f"[benchmark_realtime_daily_sales_inventory] Completed real-time benchmark for date: {processing_date}"
    )

    return {
        "mode": "real-time",
        "status": "completed",
        "processing_date": str(processing_date),
        "total_orders": total_orders,
        "orders_processed": orders_processed,
        "items_processed": items_processed,
        "missing_inventory_variants": missing_inventory_variants,
        "inventory_total_before": before_inventory_total,
        "inventory_total_after": after_inventory_total,
        "inventory_delta": after_inventory_total - before_inventory_total,
        "stock_movements_created": stock_movements_created,
        "processing_time_ms": int((benchmark_finished_at - benchmark_started_at).total_seconds() * 1000),
        "variant_changes": variant_changes,
    }


@shared_task(bind=True, acks_late=True)
def finalize_daily_sales_inventory_parallel(self, processing_record_id):
    """Finalize the parallel batch when all chunk tasks have reported back."""

    with transaction.atomic():
        processing_record = DailySalesProcessing.objects.select_for_update().get(
            pk=processing_record_id
        )

        completed_chunks = processing_record.processed_chunks + processing_record.failed_chunks

        if processing_record.status == ProcessingStatus.COMPLETED:
            return {
                "status": "completed",
                "processing_date": str(processing_record.processing_date),
                "processed_chunks": processing_record.processed_chunks,
                "failed_chunks": processing_record.failed_chunks,
                "total_chunks": processing_record.total_chunks,
            }

        if processing_record.status != ProcessingStatus.IN_PROGRESS:
            return {
                "status": processing_record.status,
                "processing_date": str(processing_record.processing_date),
                "processed_chunks": processing_record.processed_chunks,
                "failed_chunks": processing_record.failed_chunks,
                "total_chunks": processing_record.total_chunks,
            }

        if completed_chunks < processing_record.total_chunks:
            logger.info(
                f"[finalize_daily_sales_inventory_parallel] "
                f"Waiting for more chunks for {processing_record.processing_date}: "
                f"{completed_chunks}/{processing_record.total_chunks} complete"
            )
            return {
                "status": "waiting",
                "processing_date": str(processing_record.processing_date),
                "processed_chunks": processing_record.processed_chunks,
                "failed_chunks": processing_record.failed_chunks,
                "total_chunks": processing_record.total_chunks,
            }

        processing_record.status = ProcessingStatus.COMPLETED
        processing_record.save(update_fields=["status", "updated_at"])

    if processing_record.failed_chunks:
        logger.warning(
            f"[finalize_daily_sales_inventory_parallel] "
            f"Completed {processing_record.processing_date} with "
            f"{processing_record.failed_chunks} failed chunk(s)"
        )
    else:
        logger.info(
            f"[finalize_daily_sales_inventory_parallel] "
            f"Completed {processing_record.processing_date} successfully"
        )

    return {
        "status": "completed",
        "processing_date": str(processing_record.processing_date),
        "processed_chunks": processing_record.processed_chunks,
        "failed_chunks": processing_record.failed_chunks,
        "total_chunks": processing_record.total_chunks,
    }


@shared_task(bind=True, max_retries=3, acks_late=True)
def process_daily_sales_inventory_parallel(
    self,
    processing_date_str=None,
):
    """Dispatch one Celery task per chunk for parallel daily sales processing."""

    processing_date = _parse_processing_date(processing_date_str)

    logger.info(
        f"[process_daily_sales_inventory_parallel] "
        f"Starting parallel fan-out for date: {processing_date}"
    )

    processing_started_at = datetime.now()
    processing_record, created = DailySalesProcessing.objects.get_or_create(
        processing_date=processing_date,
        defaults={"status": ProcessingStatus.PENDING, "total_chunks": 0},
    )
    previous_status = processing_record.status

    if processing_record.status == ProcessingStatus.COMPLETED:
        logger.info(
            f"[process_daily_sales_inventory_parallel] "
            f"Date {processing_date} was already processed on "
            f"{processing_record.updated_at}. Skipping."
        )
        return {
            "status": "skipped",
            "reason": "Already processed",
            "processing_date": str(processing_date),
        }

    if not created and (
        processing_record.status != ProcessingStatus.PENDING
        or processing_record.processed_chunks
        or processing_record.failed_chunks
        or processing_record.last_processed_order_id
        or processing_record.error_log
    ):
        logger.warning(
            f"[process_daily_sales_inventory_parallel] "
            f"Processing record for {processing_date} is not clean. "
            f"Reset it before rerunning parallel mode."
        )
        return {
            "status": "skipped",
            "reason": "Processing record must be reset before rerunning parallel mode",
            "processing_date": str(processing_date),
        }

    orders_queryset = _get_pending_orders_queryset(processing_date)
    total_orders = orders_queryset.count()

    if total_orders == 0:
        logger.info(
            f"[process_daily_sales_inventory_parallel] "
            f"No orders found for {processing_date}. Marking as completed."
        )
        processing_record.status = ProcessingStatus.COMPLETED
        processing_record.total_chunks = 0
        processing_record.processed_chunks = 0
        processing_record.failed_chunks = 0
        processing_record.last_processed_order_id = 0
        processing_record.error_log = ""
        processing_record.save(
            update_fields=[
                "status",
                "total_chunks",
                "processed_chunks",
                "failed_chunks",
                "last_processed_order_id",
                "error_log",
                "updated_at",
            ]
        )
        return {
            "status": "completed",
            "processing_date": str(processing_date),
            "total_orders": 0,
            "total_chunks": 0,
            "processed_chunks": 0,
            "failed_chunks": 0,
            "message": "No orders to process",
            "comparison_report": {
                "before": {
                    "status": previous_status,
                    "affected_inventory_total": 0,
                    "stock_movements": 0,
                },
                "after": {
                    "status": processing_record.status,
                    "affected_inventory_total": 0,
                    "stock_movements": 0,
                },
                "comparison": {
                    "inventory_delta": 0,
                    "stock_movements_created": 0,
                    "processing_time_ms": int(
                        (datetime.now() - processing_started_at).total_seconds() * 1000
                    ),
                },
                "variant_changes": [],
            },
        }

    order_ids = list(orders_queryset.values_list("id", flat=True))
    chunk_order_groups = _split_order_ids(order_ids)
    total_chunks = len(chunk_order_groups)

    processing_record.status = ProcessingStatus.IN_PROGRESS
    processing_record.total_chunks = total_chunks
    processing_record.processed_chunks = 0
    processing_record.failed_chunks = 0
    processing_record.last_processed_order_id = 0
    processing_record.error_log = ""
    processing_record.save(
        update_fields=[
            "status",
            "total_chunks",
            "processed_chunks",
            "failed_chunks",
            "last_processed_order_id",
            "error_log",
            "updated_at",
        ]
    )

    logger.info(
        f"[process_daily_sales_inventory_parallel] "
        f"Dispatched {total_chunks} chunk task(s) for {total_orders} orders"
    )

    chunk_group = group(
        process_daily_sales_inventory_chunk.s(
            processing_record.id,
            processing_date.isoformat(),
            chunk_num + 1,
            total_chunks,
            chunk_order_ids,
        )
        for chunk_num, chunk_order_ids in enumerate(chunk_order_groups)
    )

    group_result = chunk_group.apply_async()

    logger.info(
        f"[process_daily_sales_inventory_parallel] "
        f"Group {group_result.id} queued for {processing_date}"
    )

    return {
        "status": "dispatched",
        "processing_date": str(processing_date),
        "total_orders": total_orders,
        "total_chunks": total_chunks,
        "processing_record_id": processing_record.id,
        "task_group_id": group_result.id,
    }


@shared_task(bind=True, max_retries=3, acks_late=True)
def process_daily_sales_inventory_chunk(
    self,
    processing_record_id,
    processing_date_str,
    chunk_num,
    total_chunks,
    chunk_order_ids,
):
    """Process one chunk of orders inside a Celery worker."""

    processing_date = _parse_processing_date(processing_date_str)
    worker_identity = None
    try:
        request_hostname = getattr(self.request, "hostname", None)
        worker_identity = f"{request_hostname or socket.gethostname()}:{os.getpid()}"
    except Exception:
        worker_identity = f"{socket.gethostname()}:{os.getpid()}"

    logger.info(
        f"[process_daily_sales_inventory_chunk] "
        f"CHUNK {chunk_num}/{total_chunks}: Starting with {len(chunk_order_ids)} orders (worker={worker_identity})"
    )

    try:
        chunk_orders = list(
            _get_pending_orders_queryset(processing_date).filter(
                id__in=chunk_order_ids
            )
        )

        if not chunk_orders:
            raise ValueError(
                f"Chunk {chunk_num} resolved to no orders for {processing_date}"
            )

        chunk_order_items = list(
            OrderItem.objects.filter(order_id__in=[order.id for order in chunk_orders])
            .select_related("variant")
            .order_by("order_id", "id")
        )

        inventory_updates = {}
        stock_movements_to_create = []

        for item in chunk_order_items:
            variant_id = item.variant_id
            inventory_updates[variant_id] = inventory_updates.get(variant_id, 0) - item.quantity
            stock_movements_to_create.append(
                StockMovement(
                    variant_id=variant_id,
                    movement_type=StockMovementType.DAILY_PROCESSING,
                    quantity=-item.quantity,
                    note=f"Daily sales processing for {processing_date} (Order #{item.order_id})",
                )
            )

        with transaction.atomic():
            inventory_records_to_update = []

            for variant_id in sorted(inventory_updates):
                quantity_change = inventory_updates[variant_id]
                try:
                    inventory = InventoryRecord.objects.select_for_update().select_related(
                        "variant"
                    ).get(variant_id=variant_id)
                except InventoryRecord.DoesNotExist:
                    logger.warning(
                        f"[process_daily_sales_inventory_chunk] "
                        f"CHUNK {chunk_num}/{total_chunks}: "
                        f"No inventory record found for variant {variant_id}. Skipping."
                    )
                    continue

                inventory.quantity_available = inventory.quantity_available + quantity_change
                inventory_records_to_update.append(inventory)

            if inventory_records_to_update:
                InventoryRecord.objects.bulk_update(
                    inventory_records_to_update,
                    ["quantity_available"],
                    batch_size=BULK_BATCH_SIZE,
                )

            if stock_movements_to_create:
                StockMovement.objects.bulk_create(
                    stock_movements_to_create,
                    batch_size=BULK_BATCH_SIZE,
                )

        _mark_parallel_chunk_success(processing_record_id, chunk_orders[-1].id)

        finalize_daily_sales_inventory_parallel.delay(processing_record_id)

        logger.info(
            f"[process_daily_sales_inventory_chunk] "
            f"CHUNK {chunk_num}/{total_chunks}: Completed successfully (worker={worker_identity})"
        )

        return {
            "chunk_num": chunk_num,
            "status": "completed",
            "orders": len(chunk_orders),
            "items": len(chunk_order_items),
            "variants": len(inventory_updates),
        }

    except Exception as exc:
        logger.exception(
            f"[process_daily_sales_inventory_chunk] "
            f"CHUNK {chunk_num}/{total_chunks} FAILED: {str(exc)} (worker={worker_identity})"
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)

        _append_parallel_chunk_failure(
            processing_record_id,
            chunk_num,
            str(exc),
            chunk_order_ids,
        )
        finalize_daily_sales_inventory_parallel.delay(processing_record_id)

        return {
            "chunk_num": chunk_num,
            "status": "failed",
            "error": str(exc),
            "orders": len(chunk_order_ids),
        }


@shared_task(bind=True, max_retries=3, acks_late=True)
def process_daily_sales_inventory(self, processing_date_str=None):
    """
    ETL Pipeline: Process daily sales inventory in fixed-size chunks.

    This task implements the batch-processing pattern from Session 4:
    
    1. FIXED-SIZE CHUNKING: Split the dataset into 500-record chunks
    2. ETL PIPELINE:
       - Extract: Query orders for the date
       - Transform: Calculate inventory deductions per variant
       - Load: Bulk update inventory and create stock movements
    3. IDEMPOTENCY: Track processed dates to prevent re-processing
    4. CHECKPOINTING: Log progress (chunk number, last order ID)
    5. PARTIAL FAILURE: Catch errors per chunk, log as "Dead Letter", continue
    6. DETAILED LOGGING: Log every step for monitoring

    Args:
        processing_date_str (str, optional): Date to process in 'YYYY-MM-DD' format.
                                              Defaults to today's date.

    Returns:
        dict: Summary of processing results including status, chunks processed, etc.

    Raises:
        Exception: Retried up to 3 times if processing fails catastrophically.
    """

    # ================================================================
    # SETUP: Determine which date to process
    # ================================================================
    if processing_date_str:
        try:
            processing_date = datetime.strptime(processing_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"[process_daily_sales_inventory] Invalid date format: {processing_date_str}")
            raise
    else:
        processing_date = datetime.now().date()

    logger.info(
        f"[process_daily_sales_inventory] "
        f"Starting ETL pipeline for date: {processing_date}"
    )

    processing_started_at = datetime.now()

    try:
        # ================================================================
        # IDEMPOTENCY CHECK: Has this date already been processed?
        # ================================================================
        logger.info(
            f"[process_daily_sales_inventory] "
            f"Checking if {processing_date} was already processed..."
        )

        processing_record, created = DailySalesProcessing.objects.get_or_create(
            processing_date=processing_date,
            defaults={"status": ProcessingStatus.PENDING, "total_chunks": 0},
        )

        if processing_record.status == ProcessingStatus.COMPLETED:
            logger.info(
                f"[process_daily_sales_inventory] "
                f"Date {processing_date} was already processed on "
                f"{processing_record.updated_at}. Skipping."
            )
            return {
                "status": "skipped",
                "reason": "Already processed",
                "processing_date": str(processing_date),
            }

        previous_status = processing_record.status
        checkpoint_order_id = (
            processing_record.last_processed_order_id
            if previous_status in (ProcessingStatus.IN_PROGRESS, ProcessingStatus.FAILED)
            else 0
        )
        already_processed_chunks = processing_record.processed_chunks
        existing_stock_movements = StockMovement.objects.filter(
            movement_type=StockMovementType.DAILY_PROCESSING,
            created_at__date=processing_date,
        ).count()
        inventory_before_snapshot = {}
        inventory_after_snapshot = {}
        stock_movements_created_total = 0

        # Mark as in-progress
        processing_record.status = ProcessingStatus.IN_PROGRESS
        processing_record.save(update_fields=["status", "updated_at"])

        logger.info(
            f"[process_daily_sales_inventory] "
            f"Status set to IN_PROGRESS. Processing record ID: {processing_record.id}"
        )

        if checkpoint_order_id:
            logger.info(
                f"[process_daily_sales_inventory] "
                f"Resuming from checkpoint after order ID {checkpoint_order_id}. "
                f"Already processed chunks: {already_processed_chunks}"
            )

        # ================================================================
        # EXTRACT PHASE: Query all orders from the processing date
        # ================================================================
        logger.info(
            f"[process_daily_sales_inventory] EXTRACT: "
            f"Querying orders for {processing_date}..."
        )

        orders_queryset = Order.objects.filter(
            created_at__date=processing_date,
            status=OrderStatus.PENDING,  # Only process pending orders
        ).order_by("id")

        total_orders = orders_queryset.count()

        if checkpoint_order_id:
            orders_queryset = orders_queryset.filter(id__gt=checkpoint_order_id)

        remaining_orders = orders_queryset.count()

        logger.info(
            f"[process_daily_sales_inventory] EXTRACT: "
            f"Found {total_orders} orders to process"
        )

        if checkpoint_order_id:
            logger.info(
                f"[process_daily_sales_inventory] EXTRACT: "
                f"{remaining_orders} orders remain after checkpoint resume"
            )

        if total_orders == 0 or remaining_orders == 0:
            logger.info(
                f"[process_daily_sales_inventory] "
                f"No orders found. Marking as completed."
            )
            processing_record.status = ProcessingStatus.COMPLETED
            processing_record.total_chunks = processing_record.total_chunks or 0
            processing_record.failed_chunks = 0
            processing_record.error_log = ""
            processing_record.save(
                update_fields=["status", "failed_chunks", "error_log", "updated_at"]
            )
            return {
                "status": "completed",
                "processing_date": str(processing_date),
                "total_orders": total_orders,
                "processed_orders": total_orders - remaining_orders,
                "message": "No orders to process" if total_orders == 0 else "Checkpoint already covers all orders",
                "comparison_report": {
                    "before": {
                        "status": previous_status,
                        "affected_inventory_total": 0,
                        "stock_movements": existing_stock_movements,
                    },
                    "after": {
                        "status": processing_record.status,
                        "affected_inventory_total": 0,
                        "stock_movements": existing_stock_movements,
                    },
                    "comparison": {
                        "inventory_delta": 0,
                        "stock_movements_created": 0,
                        "processing_time_ms": int((datetime.now() - processing_started_at).total_seconds() * 1000),
                    },
                    "variant_changes": [],
                },
            }

        # Calculate number of chunks needed
        total_chunks = (total_orders + CHUNK_SIZE - 1) // CHUNK_SIZE
        remaining_chunks = (remaining_orders + CHUNK_SIZE - 1) // CHUNK_SIZE
        if processing_record.total_chunks != total_chunks:
            processing_record.total_chunks = total_chunks
            processing_record.save(update_fields=["total_chunks", "updated_at"])

        logger.info(
            f"[process_daily_sales_inventory] "
            f"Dataset split into {remaining_chunks} chunk(s) of up to {CHUNK_SIZE} orders each"
        )

        # ================================================================
        # PROCESS CHUNKS: Extract → Transform → Load for each chunk
        # ================================================================
        failed_chunks_list = []
        processed_chunks = already_processed_chunks

        for chunk_num in range(remaining_chunks):
            chunk_start_idx = chunk_num * CHUNK_SIZE
            chunk_end_idx = chunk_start_idx + CHUNK_SIZE
            overall_chunk_num = already_processed_chunks + chunk_num + 1

            logger.info(
                f"[process_daily_sales_inventory] "
                f"===== CHUNK {overall_chunk_num}/{total_chunks} ====="
            )
            logger.info(
                f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                f"Processing queryset slice [{chunk_start_idx}:{chunk_end_idx}]"
            )

            try:
                # ====================================================
                # EXTRACT: Get chunk of orders
                # ====================================================
                chunk_orders = list(orders_queryset[chunk_start_idx:chunk_end_idx])

                logger.info(
                    f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                    f"EXTRACT: Retrieved {len(chunk_orders)} orders"
                )

                chunk_order_ids = [order.id for order in chunk_orders]
                chunk_order_items = list(
                    OrderItem.objects.filter(order_id__in=chunk_order_ids)
                    .select_related("variant")
                    .order_by("order_id", "id")
                )

                # ====================================================
                # TRANSFORM & LOAD: All in one atomic transaction
                # ====================================================
                logger.info(
                    f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                    f"TRANSFORM: Calculating metrics..."
                )

                with transaction.atomic():
                    # Prepare data structures for bulk operations
                    inventory_updates = {}  # variant_id -> quantity_change
                    stock_movements_to_create = []

                    # Transform: Calculate inventory changes per variant
                    for item in chunk_order_items:
                        variant_id = item.variant_id

                        # Accumulate inventory changes
                        if variant_id not in inventory_updates:
                            inventory_updates[variant_id] = 0

                        inventory_updates[variant_id] -= item.quantity

                        # Prepare stock movement record
                        stock_movements_to_create.append(
                            StockMovement(
                                variant_id=variant_id,
                                movement_type=StockMovementType.DAILY_PROCESSING,
                                quantity=-item.quantity,
                                note=f"Daily sales processing for {processing_date} (Order #{item.order_id})",
                            )
                        )

                    logger.info(
                        f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                        f"TRANSFORM: Calculated changes for {len(inventory_updates)} variants"
                    )

                    # ====================================================
                    # LOAD: Bulk update inventory records
                    # ====================================================
                    logger.info(
                        f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                        f"LOAD: Updating inventory records..."
                    )

                    inventory_records_to_update = []

                    for variant_id, quantity_change in inventory_updates.items():
                        try:
                            inventory = InventoryRecord.objects.select_for_update().get(
                                variant_id=variant_id
                            )
                            if variant_id not in inventory_before_snapshot:
                                inventory_before_snapshot[variant_id] = {
                                    "sku": inventory.variant.sku,
                                    "quantity_available": inventory.quantity_available,
                                }
                            # Row lock from select_for_update() keeps the update atomic inside this chunk.
                            inventory.quantity_available = (
                                inventory.quantity_available + quantity_change
                            )
                            inventory_after_snapshot[variant_id] = {
                                "sku": inventory.variant.sku,
                                "quantity_available": inventory.quantity_available,
                            }
                            inventory_records_to_update.append(inventory)

                        except InventoryRecord.DoesNotExist:
                            logger.warning(
                                f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                                f"No inventory record found for variant {variant_id}. Skipping."
                            )

                    # Bulk update inventory (batch size matches the chunk size)
                    if inventory_records_to_update:
                        InventoryRecord.objects.bulk_update(
                            inventory_records_to_update,
                            ["quantity_available"],
                            batch_size=BULK_BATCH_SIZE,
                        )
                        logger.info(
                            f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                            f"LOAD: Updated {len(inventory_records_to_update)} inventory records "
                            f"using bulk batches of {BULK_BATCH_SIZE}"
                        )

                    # Bulk create stock movements
                    if stock_movements_to_create:
                        StockMovement.objects.bulk_create(
                            stock_movements_to_create, batch_size=BULK_BATCH_SIZE
                        )
                        stock_movements_created_total += len(stock_movements_to_create)
                        logger.info(
                            f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                            f"LOAD: Created {len(stock_movements_to_create)} stock movements "
                            f"using bulk batches of {BULK_BATCH_SIZE}"
                        )

                    # ====================================================
                    # CHECKPOINT: Commit progress with the chunk's data
                    # ====================================================
                    processed_chunks = overall_chunk_num
                    last_order_id = chunk_orders[-1].id if chunk_orders else checkpoint_order_id

                    processing_record.processed_chunks = processed_chunks
                    processing_record.last_processed_order_id = last_order_id
                    processing_record.save(
                        update_fields=[
                            "processed_chunks",
                            "last_processed_order_id",
                            "updated_at",
                        ]
                    )

                    logger.info(
                        f"[process_daily_sales_inventory] "
                        f"✓ CHUNK {overall_chunk_num} COMPLETED "
                        f"(Checkpoint: last_order_id={last_order_id})"
                    )

            except Exception as chunk_error:
                # ====================================================
                # PARTIAL FAILURE HANDLING: Log as dead letter, continue
                # ====================================================
                logger.error(
                    f"[process_daily_sales_inventory] "
                    f"✗ CHUNK {overall_chunk_num} FAILED: {str(chunk_error)}",
                    exc_info=True,
                )

                failed_chunks_list.append(
                    {
                        "chunk_num": overall_chunk_num,
                        "error": str(chunk_error),
                        "order_range": (
                            f"{chunk_order_ids[0]}-{chunk_order_ids[-1]}"
                            if chunk_order_ids
                            else f"{chunk_start_idx}-{chunk_end_idx}"
                        ),
                    }
                )

                processing_record.failed_chunks += 1
                processing_record.save(update_fields=["failed_chunks", "updated_at"])

                # Continue to next chunk instead of aborting entire pipeline
                continue

        # ================================================================
        # FINAL SUMMARY: Log results and update processing record
        # ================================================================
        logger.info(
            f"[process_daily_sales_inventory] "
            f"===== PIPELINE SUMMARY FOR {processing_date} ====="
        )
        logger.info(
            f"[process_daily_sales_inventory] Total Orders: {total_orders}"
        )
        logger.info(f"[process_daily_sales_inventory] Total Chunks: {total_chunks}")
        logger.info(
            f"[process_daily_sales_inventory] Successfully Processed Chunks: {processed_chunks}"
        )
        logger.info(
            f"[process_daily_sales_inventory] Failed Chunks: {len(failed_chunks_list)}"
        )

        if failed_chunks_list:
            error_json = json.dumps(failed_chunks_list, indent=2)
            logger.error(
                f"[process_daily_sales_inventory] Failed chunks details:\n{error_json}"
            )
        else:
            error_json = ""

        # Determine final status
        if len(failed_chunks_list) == 0:
            processing_record.status = ProcessingStatus.COMPLETED
            logger.info(
                f"[process_daily_sales_inventory] "
                f"✓ ETL PIPELINE COMPLETED SUCCESSFULLY"
            )
        else:
            # Partial success: some chunks failed but we continued
            # This is still considered a partial completion
            processing_record.status = ProcessingStatus.COMPLETED
            logger.warning(
                f"[process_daily_sales_inventory] "
                f"⚠ ETL PIPELINE COMPLETED WITH {len(failed_chunks_list)} FAILED CHUNKS"
            )

        processing_record.failed_chunks = len(failed_chunks_list)
        processing_record.error_log = error_json
        processing_record.save(
            update_fields=[
                "status",
                "failed_chunks",
                "error_log",
                "updated_at",
            ]
        )

        before_inventory_total = sum(
            item["quantity_available"] for item in inventory_before_snapshot.values()
        )
        after_inventory_total = sum(
            item["quantity_available"] for item in inventory_after_snapshot.values()
        )
        variant_changes = []
        for variant_id, before_snapshot in inventory_before_snapshot.items():
            after_snapshot = inventory_after_snapshot.get(variant_id, before_snapshot)
            variant_changes.append(
                {
                    "sku": before_snapshot["sku"],
                    "before": before_snapshot["quantity_available"],
                    "after": after_snapshot["quantity_available"],
                    "delta": after_snapshot["quantity_available"] - before_snapshot["quantity_available"],
                }
            )

        variant_changes.sort(key=lambda item: item["sku"])

        processing_finished_at = datetime.now()
        comparison_report = {
            "before": {
                "status": previous_status,
                "affected_inventory_total": before_inventory_total,
                "stock_movements": existing_stock_movements,
            },
            "after": {
                "status": processing_record.status,
                "affected_inventory_total": after_inventory_total,
                "stock_movements": existing_stock_movements + stock_movements_created_total,
            },
            "comparison": {
                "inventory_delta": after_inventory_total - before_inventory_total,
                "stock_movements_created": stock_movements_created_total,
                "processing_time_ms": int((processing_finished_at - processing_started_at).total_seconds() * 1000),
            },
            "variant_changes": variant_changes,
        }

        # ================================================================
        # RETURN SUMMARY
        # ================================================================
        return {
            "status": processing_record.status,
            "processing_date": str(processing_date),
            "total_orders": total_orders,
            "total_chunks": total_chunks,
            "processed_chunks": processed_chunks,
            "failed_chunks": len(failed_chunks_list),
            "failed_chunk_details": failed_chunks_list,
            "comparison_report": comparison_report,
        }

    except Exception as e:
        # If something catastrophic happens, retry
        logger.exception(
            f"[process_daily_sales_inventory] "
            f"CATASTROPHIC FAILURE: Task will be retried. Error: {str(e)}"
        )

        # Update record to failed state
        try:
            processing_record.status = ProcessingStatus.FAILED
            processing_record.error_log = str(e)
            processing_record.save()
        except Exception:
            pass  # If we can't even update the record, just proceed with retry

        raise self.retry(exc=e, countdown=60)
