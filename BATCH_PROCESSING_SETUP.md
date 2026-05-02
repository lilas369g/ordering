# Batch Processing Setup

This is the short Windows runbook for the daily sales batch.

## What it does

- `process_daily_sales_batch` runs a real-time benchmark, then queues the Celery fan-out batch.
- Orders are split into chunks of 500.
- Each chunk is processed by a worker, then the finalizer marks the date complete.

## Prerequisites

- Run commands from `backend`
- Python virtualenv: `backend/.venv`
- RabbitMQ running locally, or set `CELERY_BROKER_URL`

## 1) Activate the virtualenv

```powershell
cd "C:\Users\ru\Desktop\New folder\ordering\backend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
```

## 2) Start Celery workers

Open 3 terminals and run one worker in each terminal:

```powershell
python -m celery -A config worker -l info -P solo --without-gossip --without-mingle --prefetch-multiplier=1 -n worker1@%h --logfile=worker1.log
```

Use `worker2@%h --logfile=worker2.log` and `worker3@%h --logfile=worker3.log` in the other two terminals.

## 3) Seed demo data

```powershell
python manage.py seed_demo_store
python manage.py seed_batch_demo_orders 2026-05-04 --orders 1500
```

## 4) Queue the batch

```powershell
python manage.py process_daily_sales_batch 2026-05-04 --async
```

Expected output:

- BEFORE shows the real-time benchmark
- AFTER shows the queued batch and expected chunks
- COMPARISON shows the queue time saved

## 5) Check the status in a readable format

```powershell
python manage.py show_daily_sales_processing 2026-05-04
```

This prints:

- pending orders
- chunk size
- expected chunks
- current status
- processed / failed chunks
- last processed order ID

## 6) See which workers are attached

```powershell
python manage.py show_celery_consumers --host localhost --port 15672 --user guest --password guest --queue celery
```

This shows the consumers currently attached to the `celery` queue.

It also prints chunk-to-worker mapping by reading `worker*.log` lines.

## 7) Reset the date before rerunning

Preview first:

```powershell
python manage.py reset_daily_sales_processing 2026-05-04 --dry-run
```

Then reset for real:

```powershell
python manage.py reset_daily_sales_processing 2026-05-04
```

If you need to restore the demo stock for `RICE-S` before rerunning the benchmark:

```powershell
python manage.py shell -c "from apps.inventory.models import InventoryRecord; ir=InventoryRecord.objects.get(variant__sku='RICE-S'); ir.quantity_available=7500; ir.save(update_fields=['quantity_available']); print('RICE-S stock reset to', ir.quantity_available)"
```

Run the async batch again if needed:

```powershell
python manage.py process_daily_sales_batch 2026-05-04 --async
```

## What to look for

- Worker logs should show `CHUNK 1/3`, `CHUNK 2/3`, and `CHUNK 3/3`.
- Each chunk log includes `(worker=HOST:PID)` so you can see which worker handled it.
- The finalizer should end with `processed_chunks: 3, failed_chunks: 0`.

## Quick compare mode

If you want to compare real-time vs batch without queueing first:

```powershell
python manage.py process_daily_sales_batch 2026-05-04 --compare
```
