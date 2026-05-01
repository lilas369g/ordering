# Batch Processing Setup: Step-by-Step Guide

This guide walks you through implementing and running the daily sales inventory batch processing feature.

---

## 📋 What Was Built

**Fixed-Size Chunking + ETL Pipeline** for batch processing:
- **Splits** large datasets into 500-record chunks
- **Extracts** order data, **transforms** it, **loads** it efficiently
- **Idempotent** — won't create duplicates if task retries
- **Checkpointing** — tracks progress for crash recovery
- **Partial failure handling** — one bad chunk doesn't break the whole batch
- **Detailed logging** — see every step in real-time

---

## 🚀 Step 1: Apply Database Migrations

```bash
cd backend

# Create and apply the new migration
python manage.py migrate inventory
```

This creates:
- `DailySalesProcessing` table — tracks which dates have been processed
- `ProcessingStatus` choices — pending, in_progress, completed, failed
- `StockMovementType.DAILY_PROCESSING` — audit trail for inventory changes

---

## 🚀 Step 2: Create Test Data

Seed the demo catalog first, then create test orders so we have something to batch process:

```bash
python manage.py seed_demo_store
```

Then open the Django shell:

```bash
python manage.py shell
```

Then in the Django shell:

```python
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryRecord

# Get a test user
User = get_user_model()
user = User.objects.first()

# Use one seeded demo variant and make sure its inventory is large enough
variant = ProductVariant.objects.get(sku="RICE-S")
inventory, _ = InventoryRecord.objects.update_or_create(
    variant=variant,
    defaults={
        "quantity_available": 1000,
        "low_stock_threshold": 50,
    },
)

# Delete any previous demo orders so this block is safe to rerun
TEST_TAG = "BATCH-DEMO"
Order.objects.filter(customer_name__startswith=TEST_TAG).delete()

# Create test orders
for i in range(100):
    order = Order.objects.create(
        customer=user,
        status=OrderStatus.PENDING,
        total_amount=Decimal("250.00"),
        customer_name=f"{TEST_TAG} Customer {i}",
        phone_number="1234567890",
        shipping_address=f"{TEST_TAG} Address",
        province="Test Province"
    )
    
    # Add 5 items per order
    for j in range(5):
        OrderItem.objects.create(
            order=order,
            variant=variant,
            quantity=1,
            unit_price=Decimal("50.00")
        )

print("✓ Created 100 test orders with 500 items")
print(f"✓ Initial inventory: {inventory.quantity_available} units")

exit()
```

If you already seeded the catalog once, rerunning this block will first delete
the previous demo orders with the same `BATCH-DEMO` tag, then recreate them.

**Verify:**
```bash
python manage.py shell
```

```python
from apps.orders.models import Order, OrderStatus
from datetime import datetime

today = datetime.now().date()
count = Order.objects.filter(
    created_at__date=today,
    status=OrderStatus.PENDING
).count()
print(f"Orders today: {count}")
```

---

## 🚀 Step 3: Run the Batch Processing Task (Synchronous)

This will process the orders immediately and wait for completion:

```bash
python manage.py process_daily_sales_batch
```

**Expected output:**

```
======================================================================
  DAILY SALES INVENTORY BATCH PROCESSING
======================================================================

📋 Configuration:
   Processing Date: Today (auto-detected)
   Execution Mode: Sync (Immediate)

📊 What this command does:
   1. EXTRACT: Query all PENDING orders from the date
   2. SPLIT: Divide into chunks of 500 records
   3. TRANSFORM: Calculate inventory deductions per variant
   4. LOAD: Bulk update inventory records
   5. CHECKPOINT: Track progress for crash recovery
   6. PARTIAL FAILURE: Continue on chunk errors

🚀 Triggering task...
   Running synchronously (waiting)...

[process_daily_sales_inventory] Starting ETL pipeline for date: 2026-05-01
[process_daily_sales_inventory] EXTRACT: Found 100 orders to process
[process_daily_sales_inventory] Dataset split into 1 chunks of 500 records each
[process_daily_sales_inventory] ===== CHUNK 1/1 =====
[process_daily_sales_inventory] CHUNK 1: EXTRACT: Retrieved 100 orders
[process_daily_sales_inventory] CHUNK 1: TRANSFORM: Calculated changes for 1 variants
[process_daily_sales_inventory] CHUNK 1: LOAD: Updated 1 inventory records
[process_daily_sales_inventory] CHUNK 1: LOAD: Created 500 stock movements
[process_daily_sales_inventory] ✓ CHUNK 1 COMPLETED (Checkpoint: order_id=12345)
[process_daily_sales_inventory] ===== PIPELINE SUMMARY FOR 2026-05-01 =====
[process_daily_sales_inventory] Total Orders: 100
[process_daily_sales_inventory] Successfully Processed Chunks: 1
[process_daily_sales_inventory] Failed Chunks: 0
[process_daily_sales_inventory] ✓ ETL PIPELINE COMPLETED SUCCESSFULLY

======================================================================
  ✓ BATCH PROCESSING COMPLETED
======================================================================

📊 Results:
   Status: COMPLETED
   Processing Date: 2026-05-01
   Total Orders: 100
   Total Chunks: 1
   Successfully Processed: 1
   Failed Chunks: 0

✅ Batch processing task completed.
```

---

## 🚀 Step 4: Verify Results

Check that inventory was updated correctly:

```bash
python manage.py shell
```

```python
from apps.inventory.models import InventoryRecord, StockMovement, DailySalesProcessing
from datetime import datetime

today = datetime.now().date()

# 1. Check inventory was deducted
inventory = InventoryRecord.objects.first()
print(f"Remaining inventory: {inventory.quantity_available}")
# Should show: 1000 - 500 = 500

# 2. Check stock movements were created
movements = StockMovement.objects.filter(
    movement_type='daily_processing'
).count()
print(f"Stock movements created: {movements}")
# Should show: 500

# 3. Check processing record
processing = DailySalesProcessing.objects.get(processing_date=today)
print(f"Status: {processing.status}")
print(f"Processed chunks: {processing.processed_chunks}")
print(f"Failed chunks: {processing.failed_chunks}")
# Should show: completed, 1, 0

exit()
```

---

## 🚀 Step 5: Run Asynchronously with Celery (Optional)

If you have RabbitMQ running, you can queue the task to Celery instead:

**Terminal 1 — Start the Celery worker:**

```bash
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip
```

If `celery inspect registered` fails with `transient_nonexcl_queues`, that is
RabbitMQ 4 rejecting Celery's default transient reply queue. Either enable the
deprecated feature in `rabbitmq.conf`:

```ini
deprecated_features.permit.transient_nonexcl_queues = true
```

or use RabbitMQ 3.13.x / Redis instead. Also avoid `CELERY_RESULT_BACKEND = "rpc://"` on RabbitMQ 4, because Celery uses the same transient reply-queue pattern when publishing async tasks. If you keep `CELERY_WORKER_ENABLE_REMOTE_CONTROL = False`, rely on the worker startup log and task execution logs rather than `inspect`.

**Terminal 2 — Queue the task:**

```bash
python manage.py process_daily_sales_batch --async
```

Output:
```
✓ Task queued successfully!
   Task ID: a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6
   Status: PENDING
   Check Celery worker logs for real-time progress.
```

**Terminal 1 will show:**

```
[2026-05-01 14:30:45,123: INFO/MainProcess] Task apps.orders.tasks_batch.process_daily_sales_inventory[a1b2c3d4-e5f6...] received
[2026-05-01 14:30:45,234: INFO/Worker-1] [process_daily_sales_inventory] Starting ETL pipeline...
...
```

---

## 🚀 Step 6: Process a Specific Date

Process orders from a previous date:

```bash
python manage.py process_daily_sales_batch 2026-04-30
```

Or async:

```bash
python manage.py process_daily_sales_batch 2026-04-30 --async
```

---

## 🔍 Monitoring & Debugging

### Check Processing Status

```bash
python manage.py shell
```

```python
from apps.inventory.models import DailySalesProcessing
from datetime import datetime

today = datetime.now().date()
record = DailySalesProcessing.objects.get(processing_date=today)

print(f"Status: {record.status}")
print(f"Total chunks: {record.total_chunks}")
print(f"Processed chunks: {record.processed_chunks}")
print(f"Failed chunks: {record.failed_chunks}")
print(f"Last order ID processed: {record.last_processed_order_id}")

if record.error_log:
    import json
    errors = json.loads(record.error_log)
    print(f"Errors: {json.dumps(errors, indent=2)}")
```

### Watch Logs

```bash
# View Django/Celery logs in real-time
tail -f logs/django.log | grep "process_daily_sales_inventory"

# Or in the Celery worker terminal (if running async)
# You'll see logs directly as they're processed
```

### Check Inventory Changes

```bash
python manage.py shell
```

```python
from apps.inventory.models import StockMovement, StockMovementType
from datetime import datetime

today = datetime.now().date()

# See all stock movements from batch processing
movements = StockMovement.objects.filter(
    movement_type=StockMovementType.DAILY_PROCESSING,
    created_at__date=today
)

print(f"Total movements: {movements.count()}")

# Group by variant
from django.db.models import Sum

grouped = movements.values('variant__sku').annotate(total=Sum('quantity'))
for item in grouped:
    print(f"{item['variant__sku']}: {item['total']} units deducted")
```

---

## ✅ Key Implementation Details Explained

### 1. Fixed-Size Chunking

**What:** Process 500 orders at a time (configurable)

**Why:** Prevents memory overload, allows crash recovery, faster overall

**Located in:** `apps/orders/tasks_batch.py` line 56

```python
CHUNK_SIZE = 500
```

### 2. ETL Pipeline

**What:**
- **Extract:** Query orders from database
- **Transform:** Calculate inventory changes
- **Load:** Bulk update in one atomic transaction

**Why:** Clean separation of concerns, efficient database operations

**Located in:** `apps/orders/tasks_batch.py` lines 200-350

### 3. Idempotency

**What:** Won't process the same date twice

**Why:** Prevents duplicate inventory deductions if task retries

**Located in:** `apps/orders/tasks_batch.py` lines 100-115

```python
processing_record, created = DailySalesProcessing.objects.get_or_create(
    processing_date=processing_date
)
if processing_record.status == ProcessingStatus.COMPLETED:
    return {"status": "skipped"}
```

### 4. Checkpointing

**What:** Track `processed_chunks` and `last_processed_order_id` after each chunk

**Why:** Know exactly where a crash happened and resume from the saved checkpoint on the next run

**Located in:** `apps/orders/tasks_batch.py` lines 260-270

```python
processing_record.processed_chunks = processed_chunks
processing_record.last_processed_order_id = last_order_id
processing_record.save(update_fields=["processed_chunks", "last_processed_order_id", "updated_at"])
```

### 5. Partial Failure Handling

**What:** Catch errors per chunk, log them, continue

**Why:** One bad chunk shouldn't break the whole batch

**Located in:** `apps/orders/tasks_batch.py` lines 275-295

```python
except Exception as chunk_error:
    logger.error(f"CHUNK {chunk_num + 1} FAILED...")
    failed_chunks_list.append({...})
    continue  # Don't abort, process next chunk
```

### 6. Detailed Logging

**What:** Log every major step with structured messages

**Why:** Operational visibility, debugging, monitoring

**Located in:** Throughout `apps/orders/tasks_batch.py`

```python
logger.info(f"[process_daily_sales_inventory] EXTRACT: Found {total_orders} orders")
logger.info(f"[process_daily_sales_inventory] CHUNK {chunk_num + 1}: LOAD: Updated {count} records")
```

---

## 🧪 Testing Failure Scenarios

### Simulate a Chunk Failure

Manually cause an error to test partial failure handling:

```python
# In tasks_batch.py, temporarily add:
if chunk_num == 1:  # Fail on chunk 2
    raise ValueError("Simulated chunk failure for testing")
```

Expected behavior:
- Chunk 2 fails and is logged
- Chunk 3+ continue processing
- Final status shows some chunks failed
- Can retry the failed chunk manually

### Test Idempotency

Run the same date twice:

```bash
# First run
python manage.py process_daily_sales_batch 2026-05-01

# Second run — should be skipped
python manage.py process_daily_sales_batch 2026-05-01
```

Expected: Second run returns immediately with "Already processed" message

---

## 🔧 Configuration Tuning

### Adjust Chunk Size

Edit `apps/orders/tasks_batch.py`:

```python
CHUNK_SIZE = 1000  # Larger chunks = faster but more memory
```

- **100-200:** Low memory, safer
- **500-1000:** Balanced, recommended
- **2000+:** High throughput, requires more memory

### Retry Policy

Edit `apps/orders/tasks_batch.py` line 30:

```python
@shared_task(bind=True, max_retries=3, acks_late=True)
```

- `max_retries=3`: Retry up to 3 times if catastrophic failure
- `acks_late=True`: Only mark task as done after successful completion

---

## 📚 Files Reference

| File | Purpose |
|------|---------|
| `apps/orders/tasks_batch.py` | ETL pipeline task implementation |
| `apps/orders/management/commands/process_daily_sales_batch.py` | CLI command to trigger task |
| `apps/inventory/models.py` | `DailySalesProcessing`, `ProcessingStatus` models |
| `apps/inventory/migrations/0002_batch_processing.py` | Database schema for tracking |
| `config/settings.py` | Logging & Celery configuration |
| `docs/BATCH_PROCESSING_GUIDE.md` | Detailed technical documentation |

---

## ✨ Next Steps

1. **Schedule it:** Use Celery Beat to auto-run daily at midnight
2. **Monitor it:** Export metrics to Prometheus/Grafana
3. **Scale it:** Process multiple dates in parallel
4. **Dashboard:** Build a web UI showing pipeline progress
5. **Retry logic:** Auto-retry only failed chunks

---

## ❓ Troubleshooting

**Q: "No orders to process"**  
A: Check test data exists: `Order.objects.filter(status='pending', created_at__date=today).count()`

**Q: Inventory not decreasing**  
A: Check InventoryRecord exists for the variant: `InventoryRecord.objects.count()`

**Q: All chunks failed**  
A: Check error_log: `DailySalesProcessing.objects.latest('id').error_log`

**Q: Task runs forever**  
A: Stop with `Ctrl+C`. It will retry from last checkpoint when re-run.

---

## 📞 Summary

You've successfully implemented:
- ✅ Fixed-Size Chunking (500 records/chunk)
- ✅ ETL Pipeline (Extract → Transform → Load)
- ✅ Idempotency (no duplicates on retry)
- ✅ Checkpointing (resume from crash point)
- ✅ Partial Failure (continue on errors)
- ✅ Detailed Logging (full observability)

**Next:** Run `python manage.py process_daily_sales_batch` and watch the magic happen! 🚀
