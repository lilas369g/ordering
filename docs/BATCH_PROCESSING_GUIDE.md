# Batch Processing Guide: Daily Sales Inventory

This document explains how the daily sales batch works in the code.
Use `BATCH_PROCESSING_SETUP.md` for the shortest step-by-step runbook.

## Pipeline at a glance

- Input: pending orders for a single processing date
- Chunking: 500 orders per chunk
- Flow: Extract -> Transform -> Load
- State: `DailySalesProcessing` stores progress and status
- Output: inventory updates and `daily_processing` stock movements

## Execution modes

- Sync: the management command runs the task directly in the current process.
- Async: the management command queues the same task to Celery.
- Compare: the command runs a rollbacked benchmark first, then the batch ETL on a fresh date.
- Reset: the management command clears one processed date so you can rerun it intentionally.

Async does not change the business logic. It only changes where the work runs.
The same code in `apps/orders/tasks_batch.py` is used either way.

## Core implementation details

### 1. Fixed-size chunking

`CHUNK_SIZE = 500` keeps memory usage predictable and keeps each database lock short.
The code slices the queryset into chunks and processes each chunk independently.

Why this matters:

- lower memory usage
- smaller transactions
- easier recovery after a crash

### 2. ETL pipeline

Each chunk follows the same pattern:

- Extract: query the orders and items for the selected date
- Transform: aggregate the quantity changes per variant
- Load: bulk update inventory and bulk create stock movements

Why this matters:

- clear separation of responsibilities
- fewer database round-trips
- easier to test and debug

### 3. Idempotency

`DailySalesProcessing.processing_date` is unique, so the same date is not processed twice by accident.
If the status is already `completed`, the task returns `skipped`.

Why this matters:

- protects against duplicate deductions
- makes retries safe
- keeps async execution predictable

### 4. Checkpointing

The batch record stores `processed_chunks` and `last_processed_order_id`.
That lets the next run continue from the last successful chunk instead of starting over.

Why this matters:

- crash recovery
- clearer progress reporting
- less repeated work

### 5. Partial failure handling

If one chunk fails, the task logs the error, stores it in `error_log`, and continues with later chunks.

Why this matters:

- one bad chunk does not cancel the whole job
- successful chunks are preserved
- failures can be retried or inspected later

### 6. Logging

The task writes structured log messages so you can follow progress in the worker terminal.
The setup does not create `logs/django.log` by default.

Why this matters:

- the worker terminal is the source of truth for async runs
- compare mode can be read directly from the command output
- file logging can be added later with a Django `FileHandler`

## Monitoring and troubleshooting

### Check processing status

```python
from apps.inventory.models import DailySalesProcessing

record = DailySalesProcessing.objects.get(processing_date="2026-05-01")
print(record.status)
print(record.processed_chunks, record.total_chunks)
print(record.failed_chunks)
print(record.last_processed_order_id)
```

### Watch the worker

```powershell
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip
python manage.py process_daily_sales_batch 2026-05-01 --async
```

### Common cases

- Compare says the date already exists: run `reset_daily_sales_processing` or pick a fresh date.
- No pending orders: seed the demo orders again.
- Async seems instant: the worker probably consumed the job right away, which is normal on a solo worker.
- No log file: add a Django `FileHandler` in `config/settings.py` first.

## Configuration knobs

- `CHUNK_SIZE` in `apps/orders/tasks_batch.py`
- `max_retries=3` on the Celery task
- `acks_late=True` so the task is only acknowledged after success

## File map

| File | Purpose |
|------|---------|
| `backend/apps/orders/tasks_batch.py` | Batch ETL task, benchmark helper, and comparison report |
| `backend/apps/orders/management/commands/process_daily_sales_batch.py` | CLI entry point for sync, async, and compare runs |
| `backend/apps/orders/management/commands/reset_daily_sales_processing.py` | Reset a processed date so it can be rerun |
| `backend/apps/inventory/models.py` | `DailySalesProcessing`, `ProcessingStatus`, and stock movement tracking |
| `backend/config/celery.py` | Celery task discovery |
| `BATCH_PROCESSING_SETUP.md` | Practical step-by-step runbook |

## What is intentionally not here

- long sample output dumps
- duplicated setup instructions
- screenshot tips
- walkthrough text that belongs in the setup guide
