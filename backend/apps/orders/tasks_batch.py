"""
Batch Processing Tasks: Daily Sales Inventory Processing
========================================================

This module implements a Celery task for batch processing daily sales inventory
using the ETL (Extract, Transform, Load) pipeline pattern with fixed-size chunking.

Architecture:
- Fixed-Size Chunking: Process 500 orders per chunk
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

from celery import shared_task
from django.db import transaction

from apps.inventory.models import (
    DailySalesProcessing,
    InventoryRecord,
    ProcessingStatus,
    StockMovement,
    StockMovementType,
)
from apps.orders.models import Order, OrderItem, OrderStatus


logger = logging.getLogger(__name__)

# Configuration: Number of records per chunk
CHUNK_SIZE = 500


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
            }

        # Calculate number of chunks needed
        total_chunks = (total_orders + CHUNK_SIZE - 1) // CHUNK_SIZE
        remaining_chunks = (remaining_orders + CHUNK_SIZE - 1) // CHUNK_SIZE
        if processing_record.total_chunks != total_chunks:
            processing_record.total_chunks = total_chunks
            processing_record.save(update_fields=["total_chunks", "updated_at"])

        logger.info(
            f"[process_daily_sales_inventory] "
            f"Dataset split into {remaining_chunks} chunk(s) of {CHUNK_SIZE} records each"
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
                f"Processing records {chunk_start_idx} to {chunk_end_idx}"
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
                            # Row lock from select_for_update() keeps the update atomic inside this chunk.
                            inventory.quantity_available = (
                                inventory.quantity_available + quantity_change
                            )
                            inventory_records_to_update.append(inventory)

                        except InventoryRecord.DoesNotExist:
                            logger.warning(
                                f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                                f"No inventory record found for variant {variant_id}. Skipping."
                            )

                    # Bulk update inventory (batch_size prevents memory issues)
                    if inventory_records_to_update:
                        InventoryRecord.objects.bulk_update(
                            inventory_records_to_update,
                            ["quantity_available"],
                            batch_size=100,
                        )
                        logger.info(
                            f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                            f"LOAD: Updated {len(inventory_records_to_update)} inventory records"
                        )

                    # Bulk create stock movements
                    if stock_movements_to_create:
                        StockMovement.objects.bulk_create(
                            stock_movements_to_create, batch_size=100
                        )
                        logger.info(
                            f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: "
                            f"LOAD: Created {len(stock_movements_to_create)} stock movements"
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
