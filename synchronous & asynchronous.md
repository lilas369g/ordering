# 🐇 RabbitMQ + Celery + Django: Complete Setup Guide (Windows 11)

> **Who is this for?**  
> This guide walks you through setting up asynchronous background task processing for a Django project — from zero to a fully running system with a live monitoring dashboard. No prior knowledge of message queues is assumed.

---

## 📚 Table of Contents

1. [The Big Picture — What Are We Even Building?](#1-the-big-picture)
2. [How It All Fits Together — The Three Roles](#2-how-it-all-fits-together)
3. [Prerequisites — What You Need Before Starting](#3-prerequisites)
4. [Step 1 — Install Erlang/OTP](#4-step-1--install-erlangotp)
5. [Step 2 — Install RabbitMQ Server](#5-step-2--install-rabbitmq-server)
6. [Step 3 — Fix the Erlang Cookie (CRITICAL Windows Fix)](#6-step-3--fix-the-erlang-cookie-critical-windows-fix)
7. [Step 4 — Enable the Management Dashboard](#7-step-4--enable-the-management-dashboard)
8. [Step 5 — Configure Django + Celery](#8-step-5--configure-django--celery)
9. [Step 6 — Run the Full System](#9-step-6--run-the-full-system)
10. [Understanding the RabbitMQ Dashboard](#10-understanding-the-rabbitmq-dashboard)
11. [Understanding What's Happening in the Code](#11-understanding-whats-happening-in-the-code)
12. [Dead Letter Queue (DLQ) — Handling Permanently Failed Tasks](#12-dead-letter-queue-dlq--handling-permanently-failed-tasks)
13. [Troubleshooting Common Errors](#13-troubleshooting-common-errors)

---

## 1. The Big Picture

### The Problem: Synchronous Processing Is Slow

Imagine a user clicks **"Place Order"** on an e-commerce site. The server now needs to:

1. Validate payment — 2 seconds
2. Update inventory — 1 second
3. Send confirmation email — 3 seconds
4. Notify the warehouse — 2 seconds

If done one by one, **the user waits 8 full seconds** staring at a loading screen. If any step crashes, the whole thing fails.

```
User clicks "Place Order"
        │
        ▼
[Validate Payment] ──2s──► [Update Inventory] ──1s──► [Send Email] ──3s──► [Notify Warehouse]
                                                                                      │
                                                                              User finally sees
                                                                              "Order Confirmed"
                                                                            (8 seconds later 😴)
```

### The Solution: Asynchronous Processing with a Queue

Instead of doing everything immediately, the server:
1. Validates the order (fast, critical)
2. **Throws the slow tasks into a queue** and says "someone will handle this"
3. Immediately tells the user **"Order Received!"** — in under 1 second

The slow tasks (email, inventory, warehouse) are processed **in the background** by a separate worker process — completely invisible to the user.

```
User clicks "Place Order"
        │
        ▼
[Validate Order] ──► [Put tasks in Queue] ──► "Order Received!" ✅ (< 1 second)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
             [Worker Process]    [Worker Process]
           (Send Email later)  (Update Inventory later)
```

This is what we are building. The **Queue** in the middle is RabbitMQ. The **Worker** is Celery.

---

## 2. How It All Fits Together

There are exactly three roles in this system. Understanding them makes everything else click.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   PRODUCER              BROKER (Queue)          CONSUMER            │
│   (Your Django App)     (RabbitMQ)              (Celery Worker)     │
│                                                                     │
│   Creates tasks  ──►   Stores messages  ──►   Picks up & runs      │
│   (.delay())           until processed         tasks                │
│                                                                     │
│   "I need someone      "I'm holding onto       "I got this. I'll    │
│    to send this         this task for           process it and       │
│    email."              safe-keeping."          report back."        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Role | In Your Code | Technology |
|------|-------------|------------|
| **Producer** | `simulate_async_queue` management command | Django |
| **Broker (Queue)** | The message buffer in the middle | **RabbitMQ** ← what we're installing |
| **Consumer** | `celery worker` process | Celery |

> **Key insight:** The Producer and Consumer never talk to each other directly. They only talk to the Queue. This means if your email worker crashes, the message sits safely in RabbitMQ until the worker comes back online. No data is ever lost.

---

## 3. Prerequisites

Before starting, make sure you have:

- [ ] Windows 11 (this guide is Windows-specific)
- [ ] Python 3.x installed
- [ ] Your Django project set up with a virtual environment
- [ ] `celery>=5.3` in your `requirements.txt` and installed
- [ ] PowerShell (comes with Windows — search for it in Start Menu)
- [ ] A browser (Chrome, Firefox, Edge — anything)

> **Note on why NOT Redis or Kafka:**  
> - **Kafka** is for big data pipelines processing millions of events/second. Overkill for task queues.  
> - **Amazon SQS** requires an AWS account and costs money. Not for local development.  
> - **RabbitMQ** is specifically designed for task distribution, is what Celery was originally built for, and runs entirely on your local machine for free.

---

## 4. Step 1 — Install Erlang/OTP

RabbitMQ is written in the **Erlang** programming language. Think of Erlang as the engine that RabbitMQ runs on top of — you don't use Erlang directly, but RabbitMQ cannot run without it.

### 4.1 Download Erlang

Go to: **https://www.erlang.org/downloads**

Click the **"OTP XX.X Windows 64-bit Binary File"** download link (pick the latest version).

> 📸 **Screenshot tip:** Add a screenshot of the Erlang downloads page here showing which file to click.

### 4.2 Install Erlang

1. Run the downloaded `.exe` installer
2. Click **"Next"** through all screens — the defaults are fine
3. Click **"Install"**
4. Click **"Finish"**

It installs to `C:\Program Files\Erlang OTP\` by default.

### 4.3 Verify the Installation

Open a new PowerShell window and type:

```powershell
erl
```

You should see something like:

```
Eshell V15.0 (press Ctrl+G to abort, type help(). for help)
1>
```

Type `halt().` (with the period) and press Enter to exit. If you got the shell prompt, Erlang is installed correctly.

> 📸 **Screenshot tip:** Add a screenshot of the PowerShell window showing the `Eshell V15...` output.

---

## 5. Step 2 — Install RabbitMQ Server

### 5.1 Download RabbitMQ

Go to: **https://www.rabbitmq.com/docs/install-windows**

Download the **"RabbitMQ Server X.X.X — Windows Installer"** (the `.exe` file).

> 📸 **Screenshot tip:** Add a screenshot of the RabbitMQ downloads page.

### 5.2 Install RabbitMQ

1. Run the downloaded `.exe` installer
2. Click through with all default settings
3. RabbitMQ installs itself as a **Windows Service** — this means it can run in the background automatically, even without a terminal window

### 5.3 Verify RabbitMQ is Running

Open PowerShell **as Administrator** (right-click PowerShell → "Run as administrator") and run:

```powershell
cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-4.x.x\sbin"
.\rabbitmqctl.bat status
```

Replace `4.x.x` with your actual version number. You should see a long status report beginning with:

```
Status of node rabbit@YOUR-PC-NAME ...
```

If you see errors instead, move on to Step 3 — the cookie fix usually resolves startup issues on Windows.

> 📸 **Screenshot tip:** Add a screenshot of the successful `rabbitmqctl status` output.

---

## 6. Step 3 — Fix the Erlang Cookie (CRITICAL Windows Fix)

This is the most common source of problems on Windows and the step most guides skip.

### What is the Erlang Cookie?

Erlang nodes (processes) use a shared secret file called `.erlang.cookie` to authenticate with each other. When you run `rabbitmqctl` (the CLI tool), it's actually an Erlang node trying to connect to the RabbitMQ Erlang node — and they both need to have the **identical** cookie file to communicate.

On Windows, RabbitMQ creates its cookie in `C:\Windows\` but the CLI tool looks for it in `C:\Users\<YourUsername>\`. If they don't match, every CLI command fails with a mysterious error.

### The Fix

1. Open **File Explorer**
2. Navigate to `C:\Windows\`
3. Find the file named `.erlang.cookie` (it has no extension — you may need to enable "Show hidden items" in the View menu)
4. **Copy** this file (`Ctrl+C`)
5. Navigate to `C:\Users\<YourUsername>\` (your personal user folder)
6. **Paste and overwrite** the existing `.erlang.cookie` file there (`Ctrl+V`, confirm overwrite)

> 📸 **Screenshot tip:** Add a screenshot of File Explorer showing both locations and the `.erlang.cookie` file. Enable "Show hidden items" first so it's visible.

After doing this, restart RabbitMQ from PowerShell as Administrator:

```powershell
cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-4.x.x\sbin"
.\rabbitmq-service.bat stop
.\rabbitmq-service.bat start
```

Now try `.\rabbitmqctl.bat status` again — it should work without errors.

---

## 7. Step 4 — Enable the Management Dashboard

RabbitMQ has a built-in web dashboard where you can see your queues, messages, and workers in real time. It's called the **Management Plugin** and it's not enabled by default.

### 7.1 Enable the Plugin

In PowerShell **as Administrator**:

```powershell
cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-4.x.x\sbin"
.\rabbitmq-plugins.bat enable rabbitmq_management
```

You should see output like:

```
Enabling plugins on node rabbit@YOUR-PC-NAME:
rabbitmq_management
...
started 3 plugins.
```

### 7.2 Restart RabbitMQ

```powershell
.\rabbitmq-service.bat stop
.\rabbitmq-service.bat start
```

### 7.3 Open the Dashboard

Open your browser and go to:

```
http://localhost:15672
```

Login with the default credentials:
- **Username:** `guest`
- **Password:** `guest`

You should see the RabbitMQ Management Dashboard homepage.

> 📸 **Screenshot tip:** Add a screenshot of the RabbitMQ dashboard Overview page after logging in — this is the "proof it works" screenshot.

---

## 8. Run the Full System

You need **two separate terminal windows** — one for the Worker, one to trigger tasks. Both must be in your project's `backend/` directory with the virtual environment activated.

### Terminal 1 — Start the Celery Worker (The Consumer)

```powershell
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip

#python -m celery -A config worker -l info -P solo --without-mingle --without-gossip -Q celery
```

**What each flag means:**

| Flag | What it does |
|------|-------------|
| `-A config` | Tells Celery to look for the `celery.py` app in your `config/` module |
| `worker` | Starts a worker process (the Consumer) |
| `-l info` | Sets log level to INFO so you see task activity in the terminal |
| `-P solo` | Uses the "solo" process pool — required on Windows to avoid permission errors with the default prefork pool |
| `--without-mingle` | Disables a startup handshake that causes errors with RabbitMQ 4.x |
| `--without-gossip` | Disables inter-worker gossip protocol that also causes errors with RabbitMQ 4.x |

**Successful startup looks like this:**

```
-------------- celery@YOUR-PC v5.3.6 (emerald-rush)
--- ***** -----
-- ******* ---- Windows-11-...
- *** --- * ---
- ** ---------- [config]
- ** ---------- .> app:         config:0x...
- ** ---------- .> transport:   amqp://guest:**@localhost:5672//   ← Connected!
- ** ---------- .> results:     disabled://
- *** --- * --- .> concurrency: 12 (solo)
-- ******* ----
--- ***** -----
 -------------- [queues]
                .> celery  exchange=celery(direct) key=celery

[tasks]
  . apps.orders.tasks.process_side_task

[INFO] Connected to amqp://guest:**@127.0.0.1:5672//
[INFO] mingle: searching for neighbors         ← won't appear with --without-mingle
[INFO] celery@YOUR-PC ready.                   ← This means it's waiting for work
```

> 📸 **Screenshot tip:** Add a screenshot of Terminal 1 showing the successful `celery@... ready.` output.

### Terminal 2 — Enqueue the Tasks (The Producer)

```powershell
python manage.py simulate_async_queue
```

You should immediately see:

```
Queued 3 background tasks for order ORD-123. Run a Celery worker to process them.
```

And in **Terminal 1**, watch the worker pick up and process the tasks:

```
[INFO] Task apps.orders.tasks.process_side_task[abc-123] received
Working on: Send Confirmation Email
[INFO] Task apps.orders.tasks.process_side_task[abc-123] succeeded in 2.01s

[INFO] Task apps.orders.tasks.process_side_task[def-456] received
Working on: Update Inventory Levels
[INFO] Task apps.orders.tasks.process_side_task[def-456] succeeded in 1.52s

[INFO] Task apps.orders.tasks.process_side_task[ghi-789] received
Working on: Notify Shipping Partner
[INFO] Task apps.orders.tasks.process_side_task[ghi-789] succeeded in 3.03s
```

> 📸 **Screenshot tip:** Add a side-by-side screenshot of both terminals — Terminal 2 showing the "Queued 3 tasks" message, and Terminal 1 showing the worker processing them.

---

## 10. Understanding the RabbitMQ Dashboard

Open `http://localhost:15672` in your browser. Here's what each section means.

### The Overview Tab

> 📸 **Screenshot tip:** Add a screenshot of the Overview tab with annotations on the "Total" messages graph.

The **"Queued messages"** graph shows:

| Color | Meaning |
|-------|---------|
| **Ready** (yellow) | Messages waiting in the queue — no worker has picked them up yet |
| **Unacked** (blue) | Messages a worker has received and is currently processing |
| **Total** (gray) | Ready + Unacked |

**How to see this live:**
1. Stop your Celery worker (Ctrl+C in Terminal 1)
2. Run `python manage.py simulate_async_queue` in Terminal 2
3. Watch the **Ready** count jump to 3 in the dashboard — the messages are sitting there waiting
4. Start the worker again — watch **Ready** drop to 0 and **Unacked** spike briefly as tasks are processed

This is the exact diagram from the lecture (Slide 3) but live.

### The Queues Tab

> 📸 **Screenshot tip:** Add a screenshot of the Queues tab showing the `celery` queue in the list.

Click on the **`celery`** queue in the list. You'll see:

- **Messages Ready** — tasks waiting to be picked up
- **Messages Unacknowledged** — tasks currently being processed by a worker
- **Consumers** — how many Celery workers are connected and listening

> 📸 **Screenshot tip:** Add a screenshot of the individual queue detail page.

**The "Get messages" button** (under the "Get messages" section at the bottom of the queue page) lets you peek at a message without consuming it — you can see the actual task payload that Celery serialized into JSON.

### The Connections Tab

Shows all currently connected clients. When your Celery worker is running, you'll see it listed here as an active AMQP connection from `127.0.0.1`.

> 📸 **Screenshot tip:** Add a screenshot of the Connections tab showing the Celery worker connection.

---

## 11. Understanding What's Happening in the Code

### The `.delay()` Method — How Tasks Enter the Queue

```python
# This line...
process_side_task.delay("Send Confirmation Email", 2000)

# ...is equivalent to:
# 1. Serialize the function name and arguments to JSON
# 2. Connect to RabbitMQ
# 3. Publish a message to the "celery" queue
# 4. Return immediately — the task is now RabbitMQ's problem
```

The `.delay()` call returns in milliseconds. The actual work happens later, elsewhere.

### The `@shared_task` Decorator — How Tasks Are Registered

```python
@shared_task(bind=True, max_retries=3)
def process_side_task(self, task_name, duration_ms):
    ...
```

This decorator registers `process_side_task` with Celery's task registry when the worker starts up. The worker's startup log shows which tasks it knows about:

```
[tasks]
  . apps.orders.tasks.process_side_task   ← registered and ready
```

### The Retry Mechanism — Slide 9 in Action

```python
except Exception as exc:
    raise self.retry(exc=exc, countdown=60)
```

If the task throws any exception, instead of failing permanently, Celery:
1. **Acknowledges** the current message (tells RabbitMQ "I received this, remove it from the queue")
2. Publishes a **brand new message** back into the same queue with a delay
3. Waits `countdown` seconds, then tries again — up to `max_retries=3` times

> ⚠️ **Important:** `self.retry()` does NOT put the same message back. It acknowledges the old one and creates a new one. This distinction matters a lot for Dead Letter Queues — see Section 12.

After 3 failures, the task raises `MaxRetriesExceededError`. At this point, the message is acknowledged and simply disappears — unless you explicitly configure a Dead Letter Queue (DLQ) to catch it. See Section 12 for the full implementation.

### The Producer–Consumer Separation

```
manage.py process                Celery worker process
─────────────────────            ─────────────────────────────────────
simulate_async_queue             watches the "celery" RabbitMQ queue
    │
    ├── process_side_task.delay(...)   ──► [RabbitMQ] ──► process_side_task()
    ├── process_side_task.delay(...)   ──► [RabbitMQ] ──► process_side_task()
    └── process_side_task.delay(...)   ──► [RabbitMQ] ──► process_side_task()
    
    prints "Queued 3 tasks" and exits immediately
```

The `manage.py` process doesn't wait for the tasks to finish. It queues them and exits. This is the core concept — the Producer and Consumer are **completely decoupled**.

---

## 12. Dead Letter Queue (DLQ) — Handling Permanently Failed Tasks

### What is a DLQ?

A **Dead Letter Queue** is a special queue that catches messages that could not be processed successfully — even after all retries are exhausted. Instead of silently disappearing, failed messages land in the DLQ where a developer can inspect them, understand what went wrong, and decide whether to replay them or discard them.

Think of it as a quarantine ward for sick messages.

```
Normal flow:
[celery queue] ──► [Worker] ──► SUCCESS ✅  (message acknowledged, gone)

Failure flow WITHOUT DLQ:
[celery queue] ──► [Worker] ──► FAIL ──► retry ──► FAIL ──► retry ──► FAIL ──► 💀 gone forever

Failure flow WITH DLQ (what we want):
[celery queue] ──► [Worker] ──► FAIL ──► retry ──► FAIL ──► retry ──► FAIL ──► [dead_letter_queue] 🏥
                                                                                    (inspect here)
```

In RabbitMQ's terminology:
- **DLX (Dead Letter Exchange)** — the exchange that receives rejected messages and routes them
- **DLQ (Dead Letter Queue)** — the queue bound to the DLX that holds the failed messages

### Why Native AMQP Rejection Fails on Windows `-P solo`

Three AMQP-level rejection approaches were attempted in sequence — `self.request.reject()`, `raise Reject` from kombu, `raise Reject` from celery — and all three failed silently on Celery 5.3.6 with `-P solo` on Windows. This is a confirmed behavioral issue: the `-P solo` pool on Windows does not reliably dispatch `basic_reject` AMQP frames. The task trace machinery catches `Reject` correctly, calls `req.reject()`, but the frame is never transmitted. RabbitMQ receives an acknowledgment instead, the DLX never fires, and the message disappears.

You can verify this with RabbitMQ's built-in tracing. In PowerShell as Administrator:

```powershell
cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-4.x.x\sbin"
.\rabbitmqctl.bat trace_on
```

In the dashboard: create a queue named `trace_sink`, go to the `amq.rabbitmq.trace` exchange, and bind `trace_sink` with routing key `#`. Run your failing task. In `trace_sink → Get Messages`, you will see `deliver` and `ack` entries for the FAIL task, but **no `reject` entry** — proof that `basic_reject` is never sent. Turn off after:

```powershell
.\rabbitmqctl.bat trace_off
```

---

### The Solution — Application-Level DLQ Routing

Since the AMQP rejection layer is unreliable on this stack, bypass it entirely. Instead of waiting for RabbitMQ's native DLX mechanism to fire, publish a copy of the failed message directly to `dead_letter_queue` using Celery's own producer — the same `.apply_async()` path used by every normal task. This always works regardless of pool type, OS, or Celery version.

```
AMQP-level approach (broken on -P solo / Windows):
task fails → raise Reject → trace_task → basic_reject frame → RabbitMQ DLX → DLQ
                                                    ↑
                                              never arrives

Application-level approach (always works):
task fails → MaxRetriesExceededError → current_app.send_task(..., queue='dead_letter_queue')
                                                    ↑
                                         same path as .delay() — 100% reliable
```

---

### The Complete Correct Configuration

#### `config/settings.py`

Keep the native DLX arguments — they will work correctly when this project moves to Linux or Docker where `basic_reject` works properly. On Windows with `-P solo`, the application-level routing takes over instead.

```python
from kombu import Exchange, Queue

default_exchange = Exchange('celery', type='direct')
dlx_exchange     = Exchange('dlx',    type='direct')

CELERY_TASK_QUEUES = (
    Queue(
        'celery',
        Exchange('celery'),
        routing_key='celery',
        queue_arguments={
            'x-dead-letter-exchange':    'dlx',   # active on Linux/Docker
            'x-dead-letter-routing-key': 'dlx',   # must match dead_letter_queue binding below
        }
    ),
    Queue(
        'dead_letter_queue',
        Exchange('dlx'),
        routing_key='dlx',
    ),
)

CELERY_TASK_DEFAULT_QUEUE       = 'celery'
CELERY_TASK_DEFAULT_EXCHANGE    = 'celery'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'celery'

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_ENABLE_REMOTE_CONTROL       = False
```

#### `apps/orders/tasks.py` — Final Working Version

```python
import time
from celery import current_app, shared_task
from celery.exceptions import MaxRetriesExceededError

@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_side_task(self, task_name, duration_ms):

    # ── GUARD: if this message arrived from dead_letter_queue, do not re-execute.
    # Without this, a worker consuming dead_letter_queue would re-run the failing
    # code, fail again, re-route to DLQ, and loop forever.
    if self.request.delivery_info.get('routing_key') == 'dead_letter_queue':
        print(f"[DLQ INSPECTOR] '{task_name}' is in quarantine. "
              f"Reason: {self.request.headers.get('x-death-reason', 'unknown')}")
        return  # acknowledged and done — message stays visible in dashboard

    if "FAIL" in task_name.upper():
        print(f"!!! Intentional Failure: {task_name} "
              f"(Attempt {self.request.retries + 1}/{self.max_retries + 1})")
        try:
            raise ValueError("Simulated system crash for DLQ testing.")
        except Exception as exc:
            try:
                raise self.retry(exc=exc, countdown=5)
            except MaxRetriesExceededError:
                # ── APPLICATION-LEVEL DLQ ROUTING ──────────────────────────
                # raise Reject() fails silently on Celery 5.3.6 -P solo on
                # Windows — basic_reject frames are never dispatched.
                # Instead: publish directly to dead_letter_queue via Celery's
                # own producer. Same path as .delay() — always reliable.
                # ───────────────────────────────────────────────────────────
                current_app.send_task(
                    self.name,
                    args=self.request.args,
                    kwargs=self.request.kwargs,
                    queue='dead_letter_queue',
                    headers={
                        'x-death-reason':   str(exc),
                        'x-original-queue': 'celery',
                        'x-retry-count':    str(self.max_retries),
                        'x-task-id':        self.request.id,
                    }
                )
                print(f"[DLQ] Routed '{task_name}' to dead_letter_queue "
                      f"after {self.max_retries + 1} attempts.")
                return  # return (not raise) — acks the current message cleanly

    print(f"Working on: {task_name}")
    time.sleep(duration_ms / 1000)
    return f"Finished {task_name}"
```

---

### Clean Reset Procedure

```
Step 1 — Dashboard → Queues tab
  → Delete 'celery'
  → Delete 'dead_letter_queue'

Step 2 — Dashboard → Exchanges tab
  → Delete 'dlx'        ← exchanges persist independently of queues
  (leave built-in exchanges: amq.direct, amq.fanout, amq.topic etc.)

Step 3 — Start the worker FIRST
  python -m celery -A config worker -l info -P solo --without-mingle --without-gossip
  Wait for: "celery@DESKTOP ready."

Step 4 — Then run the producer
  python manage.py simulate_async_queue
```

> 📸 **Screenshot tip:** Add a screenshot of the Exchanges tab — most users don't know it exists. Annotate the `dlx` exchange row and the Delete button.

---

### What `acks_late=True` and `reject_on_worker_lost=True` Do

| Option | Without it | With it |
|--------|-----------|---------|
| `acks_late=True` | Message acknowledged when worker *receives* it — if the worker crashes mid-task, message is gone | Message acknowledged only after task *finishes* — crash means message stays in queue |
| `reject_on_worker_lost=True` | If worker is killed, unacked message is requeued into main queue forever | If worker is killed, message is rejected → triggers DLX → goes to DLQ |

---

### The Complete Flow — Application-Level Routing

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                   FULL SYSTEM WITH DLQ (APPLICATION-LEVEL)                  │
│                                                                              │
│  celery queue         Celery Worker           dead_letter_queue              │
│  ─────────────        ─────────────           ─────────────────             │
│                                                                              │
│  [email MSG]  ──►  process_side_task  ──► SUCCESS ──► ack ✅                │
│                                                                              │
│  [FAIL MSG]   ──►  process_side_task  ──► ValueError                        │
│                           │                                                  │
│                    self.retry() × 3  ←── new messages back in celery queue  │
│                           │                                                  │
│                    MaxRetriesExceededError                                   │
│                           │                                                  │
│                    current_app.send_task(                                    │
│                        queue='dead_letter_queue'  ─────────────────────────►│
│                    )                               [FAIL MSG + headers] 🏥   │
│                           │                        (inspect in dashboard)    │
│                           │                                                  │
│                    return  ──► ack current message cleanly ✅                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Verification — Expected Worker Output

```
Working on: Send Confirmation Email
Task ... succeeded in 2.0s
Working on: Update Inventory Levels
Task ... succeeded in 1.5s
Working on: Notify Shipping Partner
Task ... succeeded in 3.0s
!!! Intentional Failure: CRITICAL_FAIL_TASK (Attempt 1/4)
Task ... retry: Retry in 5s
!!! Intentional Failure: CRITICAL_FAIL_TASK (Attempt 2/4)
Task ... retry: Retry in 5s
!!! Intentional Failure: CRITICAL_FAIL_TASK (Attempt 3/4)
Task ... retry: Retry in 5s
!!! Intentional Failure: CRITICAL_FAIL_TASK (Attempt 4/4)
[DLQ] Routed 'CRITICAL_FAIL_TASK' to dead_letter_queue after 4 attempts.
Task ... succeeded in 0.0s       ← current message acknowledged cleanly
```

**Dashboard → Queues tab:**
```
celery            │ 0 ready   ← cleared
dead_letter_queue │ 1 ready   ← the failed task is here ✅
```

**Dashboard → dead_letter_queue → Get Messages** — task payload plus custom headers: `x-death-reason`, `x-original-queue`, `x-retry-count`, `x-task-id`.

### Verifying It Works in the Dashboard

After applying the fix and running `simulate_async_queue`:

1. Open **http://localhost:15672** → Queues tab
2. You should see **two queues**: `celery` and `dead_letter_queue`
3. The `celery` queue will process the normal tasks (email, inventory, shipping) to completion
4. After the `CRITICAL_FAIL_TASK` exhausts its 3 retries, the `dead_letter_queue` should show **1 message Ready**
5. Click on `dead_letter_queue` → scroll to **"Get messages"** → click "Get Message(s)" — you can inspect the exact payload of the failed task

> 📸 **Screenshot tip:** Add a screenshot of the Queues tab showing both `celery` (0 messages) and `dead_letter_queue` (1 message) after the test run. This is the proof the DLQ is working.

---

## 13. Troubleshooting Common Errors

### ❌ `[WinError 10061] No connection could be made`

```
consumer: Cannot connect to amqp://guest:**@127.0.0.1:5672//: 
[WinError 10061] No connection could be made because the target machine actively refused it.
```

**Cause:** RabbitMQ is not running.  
**Fix:** Open PowerShell as Administrator and run:
```powershell
cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-4.x.x\sbin"
.\rabbitmq-service.bat start
```

### ❌ `rabbitmqctl` Hangs or Returns Cookie Error

```
Error: unable to perform an operation on node 'rabbit@YOUR-PC'.
```

**Cause:** Erlang cookie mismatch between the server and CLI tool.  
**Fix:** Repeat [Step 3 — Fix the Erlang Cookie](#6-step-3--fix-the-erlang-cookie-critical-windows-fix).

### ❌ `AttributeError: 'NoneType' object has no attribute 'Redis'`

```
AttributeError: 'NoneType' object has no attribute 'Redis'
```

**Cause:** You set `CELERY_BROKER_URL` to a `redis://` URL but the `redis` Python package isn't installed.  
**Fix:** Either install Redis (`pip install redis`) or remove the environment variable and use RabbitMQ (the default):
```powershell
Remove-Item Env:CELERY_BROKER_URL
```

### ❌ Tasks Print But Don't Actually Run Async

```
Working on: Send Confirmation Email
Working on: Update Inventory Levels
...
Queued 3 background tasks...
```

**Cause:** `CELERY_TASK_ALWAYS_EAGER=True` is set. This makes tasks run synchronously in the same process — it bypasses the queue entirely.  
**Fix:** Remove the environment variable:
```powershell
Remove-Item Env:CELERY_TASK_ALWAYS_EAGER
```

### ❌ Worker Starts but Gets `CPendingDeprecationWarning`

```
CPendingDeprecationWarning: The broker_connection_retry configuration setting 
will no longer determine whether broker connection retries are made during startup...
```

**Cause:** This is just a warning, not an error. Celery is telling you to add a setting before Celery 6.0 changes behavior.  
**Fix:** Add to `settings.py`:
```python
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
```

### ❌ DLQ Never Receives Messages (All Rejection Approaches Fail)

```
[DLQ] Routed 'CRITICAL_FAIL_TASK' to dead_letter_queue after 4 attempts.
# But dead_letter_queue stays at 0 messages
```

**Cause:** Celery 5.3.6 with `-P solo` on Windows does not reliably dispatch `basic_reject` AMQP frames. All AMQP-level rejection approaches (`self.request.reject()`, `raise Reject` from kombu, `raise Reject` from celery) silently fail — the message gets acknowledged instead and RabbitMQ's DLX never fires. You can verify this by enabling RabbitMQ tracing (`rabbitmqctl trace_on`) and checking for the absence of `reject` frames.

**Fix:** Use application-level DLQ routing — publish directly to `dead_letter_queue` via `current_app.send_task()` when `MaxRetriesExceededError` is caught. This uses the same producer path as `.delay()` and works on all environments. Add the infinite-loop guard at the top of the task. See [Section 12](#12-dead-letter-queue-dlq--handling-permanently-failed-tasks) for the full implementation.

### ❌ DLQ Looks Empty Even Though Logs Say "Sending to DLQ"

```
[DLQ] Routed 'CRITICAL_FAIL_TASK' to dead_letter_queue after 4 attempts.
# but dashboard still shows dead_letter_queue = 0 ready
```

**Cause:** Your worker is consuming `dead_letter_queue` too. If one worker listens to both `celery` and `dead_letter_queue`, the DLQ message is consumed immediately after it is published. In logs this appears as:

```
Task ... received
[DLQ INSPECTOR] 'CRITICAL_FAIL_TASK' is in quarantine...
Task ... succeeded
```

This means DLQ worked, but the message did not stay in the queue long enough to appear as `Ready`.

**Fix (recommended for demo/inspection):**

1. Start the main worker on the main queue only:

```powershell
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip -Q celery
```

2. Run the producer:

```powershell
python manage.py simulate_async_queue
```

3. Check dashboard: `dead_letter_queue` should now show `Ready = 1`.

4. Optional: inspect DLQ later with a separate worker:

```powershell
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip -Q dead_letter_queue
```

---

## Quick Reference — Start Everything

After initial setup, this is all you need every time:

```powershell
# Terminal 1: Start the worker
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip -Q celery

# Terminal 2: Trigger tasks (including the DLQ test)
python manage.py simulate_async_queue

# Optional Terminal 3: Inspect DLQ messages (start only when needed)
python -m celery -A config worker -l info -P solo --without-mingle --without-gossip -Q dead_letter_queue

# Browser: Monitor everything
# http://localhost:15672  (guest / guest)
# Check the Queues tab — you should see both 'celery' and 'dead_letter_queue'
```

RabbitMQ starts automatically with Windows as a service — you don't need to manually start it each time.

---

## Concept Map — Everything Connected

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         YOUR COMPLETE SYSTEM                                     │
│                                                                                  │
│  Django App (manage.py)      RabbitMQ                    Celery Worker           │
│  ─────────────────────       ─────────────────────       ─────────────────────   │
│                                                                                  │
│  simulate_async_queue        Port 5672                   process_side_task       │
│         │                ┌───────────────────┐                  │               │
│         │  .delay() ──►  │  [celery queue]   │ ────────────────►│               │
│         │  .delay() ──►  │  [MSG][MSG][MSG]  │  task received   │               │
│         │  .delay() ──►  │                   │                  ▼               │
│         │                │  x-dead-letter    │            SUCCESS → ack ✅       │
│         │                │  exchange: 'dlx'  │            FAIL → retry (new msg) │
│         │                └───────────────────┘            FAIL → retry (new msg) │
│         │                         │                       FAIL → MaxRetries      │
│         │                         │                              │               │
│         │                         │                    reject(requeue=False) ──► │
│         │                         ▼                                              │
│         │                ┌───────────────────┐                                  │
│         │                │  [dlx exchange]   │                                  │
│         │                └────────┬──────────┘                                  │
│         │                         │                                              │
│         │                         ▼                                              │
│         │                ┌───────────────────┐                                  │
│         │                │ [dead_letter_queue]│ ← inspect failed tasks here 🏥  │
│         │                │  [FAILED_MSG]     │                                  │
│         │                └───────────────────┘                                  │
│         │                                                                        │
│         └── returns instantly                                                    │
│              "Queued tasks"          Dashboard: http://localhost:15672           │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```