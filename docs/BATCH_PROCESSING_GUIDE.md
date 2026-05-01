# Batch Processing Implementation: Daily Sales Inventory

## Overview

This document explains the **Fixed-Size Chunking + ETL Pipeline** implementation for daily sales inventory batch processing, as taught in Session 4.

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│         BATCH PROCESSING PIPELINE FOR DAILY SALES                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Input: All PENDING orders from a specific date                     │
│    │                                                                │
│    ▼                                                                │
│  FIXED-SIZE CHUNKING (500 records per chunk)                        │
│    │                                                                │
│    ├─► CHUNK 1 ──┐                                                  │
│    ├─► CHUNK 2 ──┤                                                  │
│    ├─► CHUNK 3 ──┼─► EXTRACT ──► TRANSFORM ──► LOAD               │
│    ├─► CHUNK N ──┤                             (Bulk Update)       │
│    │             │                                                  │
│    ▼             ▼                                                  │
│  DailySalesProcessing (Track Status)                                │
│    │                                                                │
│    ▼                                                                │
│  Output: Updated Inventory + Stock Movements                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. Fixed-Size Chunking

### Why Chunking?

Processing 1 million orders at once would:
- Consume massive memory
- Lock the database for too long
- Crash if the worker dies mid-process

**Solution:** Split into 500-record chunks. Process each independently.

### Implementation

```python
CHUNK_SIZE = 500
total_chunks = (total_orders + CHUNK_SIZE - 1) // CHUNK_SIZE

for chunk_num in range(total_chunks):
    chunk_start_idx = chunk_num * CHUNK_SIZE
    chunk_end_idx = chunk_start_idx + CHUNK_SIZE
    
    chunk_orders = list(orders_queryset[chunk_start_idx:chunk_end_idx])
    # Process this chunk...
```

**Benefits:**
- Lower memory footprint per chunk
- Shorter database locks
- Can resume from checkpoint if crash occurs

---

## 2. ETL Pipeline

Each chunk goes through three phases:

### Phase 1: EXTRACT
**Query the data we need to process**

```python
chunk_orders = list(orders_queryset[chunk_start_idx:chunk_end_idx])
order_items = OrderItem.objects.filter(order__in=chunk_orders)
```

**What we extract:**
- All orders from the processing date (PENDING status only)
- All items within those orders
- Inventory records for affected variants

### Phase 2: TRANSFORM
**Calculate what needs to change**

```python
inventory_updates = {}  # variant_id -> quantity_change

for order in chunk_orders:
    for item in order.items.all():
        variant_id = item.variant_id
        if variant_id not in inventory_updates:
            inventory_updates[variant_id] = 0
        
        # Deduct inventory for this sale
        inventory_updates[variant_id] -= item.quantity
```

**What we transform:**
- Aggregate inventory changes by variant
- Prepare stock movement records for audit trail
- Calculate total sales impact

### Phase 3: LOAD
**Persist changes to database**

```python
# Bulk update inventory in one operation (atomic)
InventoryRecord.objects.bulk_update(
    inventory_records_to_update,
    ['quantity_available'],
    batch_size=100
)

# Bulk create stock movements for audit trail
StockMovement.objects.bulk_create(
    stock_movements_to_create,
    batch_size=100
)
```

**Why bulk operations?**
- One INSERT/UPDATE statement instead of 500+
- Dramatically faster than individual saves
- Reduces database round-trips

---

## 3. Idempotency (Preventing Duplicates)

### The Problem

If the Celery worker crashes during processing, the task will retry. Without idempotency:
- Orders might be deducted from inventory twice
- Stock movements might be duplicated
- Data becomes corrupted

### The Solution

**Track processed dates using `DailySalesProcessing` model:**

```python
processing_record, created = DailySalesProcessing.objects.get_or_create(
    processing_date=processing_date,
    defaults={"status": ProcessingStatus.PENDING}
)

if processing_record.status == ProcessingStatus.COMPLETED:
    logger.info(f"Date {processing_date} already processed. Skipping.")
    return {"status": "skipped"}
```

**How it works:**
1. First run: Record is created with `status=PENDING`
2. After successful completion: `status=COMPLETED`
3. Retry/second run: Sees `status=COMPLETED`, skips immediately
4. No duplicates! ✓

**Database Structure:**
```
DailySalesProcessing
├── processing_date: 2026-05-01 (UNIQUE)
├── status: "completed"
├── total_chunks: 5
├── processed_chunks: 5
└── failed_chunks: 0
```

---

## 4. Checkpointing (Crash Recovery)

### The Problem

If a worker crashes on chunk 3 of 10, how do we know which chunks were done?

### The Solution

**Track progress in the `DailySalesProcessing` record and save it with the chunk commit:**

```python
# After each chunk succeeds, inside the same chunk transaction:
processing_record.processed_chunks = processed_chunks  # e.g., 3
processing_record.last_processed_order_id = chunk_orders[-1].id
processing_record.save(update_fields=[
    "processed_chunks",
    "last_processed_order_id",
    "updated_at",
])

logger.info(f"✓ CHUNK {chunk_num + 1} COMPLETED (Checkpoint: order_id={last_order_id})")
```

**Monitoring Progress:**
```python
# In the dashboard or monitoring system:
processing_record = DailySalesProcessing.objects.get(processing_date='2026-05-01')
print(f"Progress: {processing_record.processed_chunks}/{processing_record.total_chunks}")
# Output: Progress: 3/10
```

**Benefits:**
- Know exactly where the crash happened
- Can resume from the next chunk instead of re-processing already committed work
- Prevents duplicate inventory deductions on retry

---

## 5. Partial Failure Handling (Dead Letter Pattern)

### The Problem

If chunk 5 fails (e.g., corrupt data, database lock), what happens?
- Option A: Abort entire pipeline (data loss!)
- Option B: Continue with remaining chunks (better!)

### The Solution

**Catch per-chunk errors, log them, continue:**

```python
for chunk_num in range(total_chunks):
    try:
        # Process chunk...
        
    except Exception as chunk_error:
        # PARTIAL FAILURE: Log as "dead letter"
        logger.error(f"✗ CHUNK {chunk_num + 1} FAILED: {str(chunk_error)}")
        
        failed_chunks_list.append({
            "chunk_num": chunk_num + 1,
            "error": str(chunk_error),
        })
        
        processing_record.failed_chunks += 1
        processing_record.save()
        
        # Continue to next chunk instead of aborting
        continue
```

**Failure Log (Stored in DB):**
```json
{
  "failed_chunks": [
    {
      "chunk_num": 5,
      "error": "Database lock timeout",
      "order_range": "2500-2999"
    }
  ]
}
```

**Retrying Failed Chunks:**
- Check `DailySalesProcessing.error_log` for which chunks failed
- Manually requeue just those chunks
- Or create a retry task that processes only failed orders

---

## 6. Detailed Logging

Every step is logged for monitoring:

```
[process_daily_sales_inventory] Starting ETL pipeline for date: 2026-05-01
[process_daily_sales_inventory] EXTRACT: Found 3500 orders to process
[process_daily_sales_inventory] Dataset split into 7 chunks of 500 records each
[process_daily_sales_inventory] ===== CHUNK 1/7 =====
[process_daily_sales_inventory] CHUNK 1: EXTRACT: Retrieved 500 orders
[process_daily_sales_inventory] CHUNK 1: TRANSFORM: Calculated changes for 342 variants
[process_daily_sales_inventory] CHUNK 1: LOAD: Updated 342 inventory records
[process_daily_sales_inventory] CHUNK 1: LOAD: Created 1250 stock movements
[process_daily_sales_inventory] ✓ CHUNK 1 COMPLETED (Checkpoint: order_id=12345)
...
[process_daily_sales_inventory] ===== PIPELINE SUMMARY FOR 2026-05-01 =====
[process_daily_sales_inventory] Total Orders: 3500
[process_daily_sales_inventory] Successfully Processed Chunks: 7
[process_daily_sales_inventory] Failed Chunks: 0
[process_daily_sales_inventory] ✓ ETL PIPELINE COMPLETED SUCCESSFULLY
```

---

## How to Run

### 1. Create the Database Migration

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

### 2. Run the Batch Processing Task

**Synchronously (wait for completion):**
```bash
python manage.py process_daily_sales_batch
```

**For a specific date:**
```bash
python manage.py process_daily_sales_batch 2026-05-01
```

**Asynchronously (queue to Celery):**
```bash
python manage.py process_daily_sales_batch --async
```

**With eager execution (for testing):**
```bash
python manage.py process_daily_sales_batch --eager
```

### 3. Monitor Progress

**Check status from database:**
```python
from apps.inventory.models import DailySalesProcessing

record = DailySalesProcessing.objects.get(processing_date='2026-05-01')
print(f"Status: {record.status}")
print(f"Progress: {record.processed_chunks}/{record.total_chunks}")
print(f"Failed: {record.failed_chunks}")
print(f"Error Log: {record.error_log}")
```

**Watch real-time logs:**
```bash
# In another terminal, follow Django logs
tail -f logs/django.log | grep "process_daily_sales_inventory"
```

---

## Configuration

### Chunk Size

Edit `CHUNK_SIZE` in `apps/orders/tasks_batch.py`:

```python
CHUNK_SIZE = 500  # Records per chunk
```

- **Smaller chunks** (100): Lower memory, slower overall
- **Larger chunks** (1000): Higher memory, faster overall
- **Sweet spot**: 500-1000 depending on your data

### Retry Policy

```python
@shared_task(bind=True, max_retries=3, acks_late=True)
```

- `max_retries=3`: Retry up to 3 times if catastrophic failure
- `acks_late=True`: Don't mark as done until truly complete

---

## Key Design Decisions

| Decision | Why |
|----------|-----|
| Fixed-Size Chunking (not Map/Reduce) | Simpler to implement, works well for uniform data |
| ETL Pattern | Clear separation: Extract (query), Transform (calculate), Load (persist) |
| `DailySalesProcessing` model | Ensures idempotency and provides checkpoint |
| Partial failure handling | Don't lose 9/10 chunks' worth of work over 1 bad chunk |
| Bulk operations | 500 individual saves → 1 bulk update (100x faster) |
| Detailed logging | Operability: understand what's happening without debugging code |

---

## Future Enhancements

1. **Scheduled Execution**: Use Celery Beat to auto-run daily at midnight
2. **Multi-date Processing**: Process N days in one task
3. **Parallel Chunks**: Process multiple chunks concurrently (requires locks)
4. **Metrics Export**: Send Prometheus metrics (chunks/sec, inventory delta)
5. **Dead Letter Retry**: Auto-requeue only failed chunks
6. **Dashboard**: Web UI showing pipeline progress in real-time

---

## Testing

### Create Test Data

```python
from datetime import datetime, timedelta
from apps.orders.models import Order, OrderStatus
from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryRecord

# Create test orders for today
today = datetime.now().date()
for i in range(50):
    order = Order.objects.create(
        customer_id=1,
        status=OrderStatus.PENDING,
        total_amount=100.00,
        customer_name=f"Test Customer {i}",
        phone_number="1234567890",
        shipping_address="Test Address",
        province="Test Province"
    )
```

### Run the Task

```bash
python manage.py process_daily_sales_batch
```

### Verify Results

```python
from apps.inventory.models import DailySalesProcessing, StockMovement

# Check processing record
record = DailySalesProcessing.objects.latest('created_at')
print(f"Status: {record.status}")
print(f"Processed: {record.processed_chunks} chunks")

# Check stock movements created
movements = StockMovement.objects.filter(
    movement_type='daily_processing'
).count()
print(f"Stock movements: {movements}")
```

---

## Troubleshooting

### All Chunks Failed

**Symptom:** `failed_chunks = total_chunks`

**Causes:**
1. No PENDING orders on that date
2. Missing InventoryRecord for some variants
3. Database connection issue

**Fix:**
- Check inventory records exist: `InventoryRecord.objects.count()`
- Check order date is correct: `Order.objects.filter(created_at__date=target_date)`

### Worker Crash

**Symptom:** Task stops mid-pipeline

**Recovery:**
1. Check `DailySalesProcessing.processed_chunks`
2. Fix the underlying issue
3. Re-run the task
4. It will skip already-processed chunks (idempotency!)

### High Memory Usage

**Symptom:** Worker becomes slow

**Solution:** Reduce `CHUNK_SIZE` from 500 to 100-200

---

## Summary

This implementation follows the **Session 4 teaching**:
- ✅ Fixed-Size Chunking: Split data into 500-record chunks
- ✅ ETL Pipeline: Extract → Transform → Load pattern
- ✅ Idempotency: `DailySalesProcessing` model ensures no duplicates
- ✅ Checkpointing: Track `processed_chunks`, `last_processed_order_id`
- ✅ Partial Failure: Catch per-chunk errors, continue
- ✅ Detailed Logging: Log every step for operability

Result: **Fast, reliable, crash-resistant batch processing!** 🚀
