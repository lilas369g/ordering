# Batch Processing Setup

This is the practical runbook for testing daily sales batch processing.
Use this file when you want the shortest path from seeded data to a visible
before/after comparison.

## What each mode does

- `--compare` runs a synchronous benchmark first, then the batch ETL, and prints a before/after comparison.
- `--async` queues the same batch task to Celery so the worker runs it in the background.
- `reset_daily_sales_processing` clears one processed date so you can rerun it intentionally.

## Fresh Demo Run

Use a fresh date that still has pending orders and has not been processed yet.

1. Open PowerShell, go to `backend`, and activate the virtual environment.

```powershell
cd "C:\Users\ru\Desktop\New folder\ordering\backend"
.\.venv\Scripts\Activate.ps1
```

2. Seed the demo catalog.

```powershell
python manage.py seed_demo_store
```

3. Seed the demo orders for one date.

```powershell
python manage.py seed_batch_demo_orders 2026-05-04
```

4. Verify that the pending orders exist.

```powershell
python manage.py shell
```

```python
from datetime import datetime
from apps.orders.models import Order, OrderStatus

target_date = datetime(2026, 5, 4).date()
demo_tag = "BATCH-DEMO"

print(
    Order.objects.filter(
        customer_name__startswith=demo_tag,
        status=OrderStatus.PENDING,
    ).count()
)
print(
    Order.objects.filter(
        created_at__date=target_date,
        status=OrderStatus.PENDING,
    ).count()
)
```

Expected result: both counts should be `100`.

5. Run the compare command.

```powershell
python manage.py process_daily_sales_batch 2026-05-04 --compare
```

What you should see:

- BEFORE = real-time benchmark
- AFTER = batch ETL
- COMPARISON = time saved, inventory delta, stock movements, and order counts

If the command says the date already has a processing record, run the reset
command first and then retry compare.

```powershell
python manage.py reset_daily_sales_processing 2026-05-04
```

Use `--dry-run` if you want to preview what will be removed.

```powershell
python manage.py reset_daily_sales_processing 2026-05-04 --dry-run
```

## Why async is useful in the code

Async does not change the ETL logic. It changes where the work runs.
The same task stays in `apps/orders/tasks_batch.py`, but Celery executes it in
the background instead of blocking the shell or a request.

That gives you these benefits:

- the command returns immediately
- the worker can retry the job if it crashes
- you can scale to more workers later without rewriting the ETL
- the same processing code can be used from CLI, Celery, or a future API trigger

On Windows with a solo worker, the main value is responsiveness and queueing,
not parallel throughput.

## Run the batch in the background

1. Start the Celery worker.

```powershell
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip
```

2. Queue the batch.

```powershell
python manage.py process_daily_sales_batch 2026-05-04 --async
```

3. Watch the worker terminal.

The worker log is the source of truth. This project does not create
`logs/django.log` by default.

## Troubleshooting

- If compare refuses to run, the date already has a processing record. Reset it or use a fresh date.
- If the compare run finds no pending orders, seed the demo orders again.
- If you are using `--async`, the task may finish too fast to show a queue backlog. That is normal.
- If you want a file log like `logs/django.log`, you must add a Django `FileHandler` in `config/settings.py` first.

## Related files

| File | Purpose |
|------|---------|
| `backend/apps/orders/tasks_batch.py` | Batch ETL task and benchmark helper |
| `backend/apps/orders/management/commands/process_daily_sales_batch.py` | CLI entry point for sync, async, and compare runs |
| `backend/apps/orders/management/commands/reset_daily_sales_processing.py` | Reset a processed date so it can be rerun |
| `docs/BATCH_PROCESSING_GUIDE.md` | Technical explanation of the implementation |
| `BATCH_PROCESSING_IMPLEMENTATION.md` | High-level implementation summary |
