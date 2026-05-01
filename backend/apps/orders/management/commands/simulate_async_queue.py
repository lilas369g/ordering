import time
from django.core.management.base import BaseCommand
from apps.orders.tasks import process_side_task

class Command(BaseCommand):
    help = "Demonstrate Before (Sync) vs After (Async) and DLQ failure handling."

    def handle(self, *args, **options):
        # ---------------------------------------------------------
        # 1. BEFORE (المشكلة) - Synchronous Processing
        # ---------------------------------------------------------
        self.stdout.write("\n==================================================")
        self.stdout.write("1. BEFORE: Synchronous Processing")
        self.stdout.write("==================================================")
        self.stdout.write("User clicks 'Place Order'... waiting...")

        start_time_sync = time.time()
        
        # Keep the original 3 tasks
        process_side_task("Send Confirmation Email", 2000)
        process_side_task("Update Inventory Levels", 1500)
        process_side_task("Notify Shipping Partner", 3000)
        
        sync_duration = (time.time() - start_time_sync) * 1000
        self.stdout.write(f"[Log] Order completed. User wait time: {sync_duration:.0f}ms.")

        # ---------------------------------------------------------
        # 2. AFTER (الحل) - Asynchronous Processing with RabbitMQ
        # ---------------------------------------------------------
        self.stdout.write("\n==================================================")
        self.stdout.write("2. AFTER: Asynchronous Processing (RabbitMQ)")
        self.stdout.write("==================================================")
        self.stdout.write("User clicks 'Place Order'... throwing tasks to queue...")

        start_time_async = time.time()
        
        # Keep the original 3 tasks
        process_side_task.delay("Send Confirmation Email", 2000)
        process_side_task.delay("Update Inventory Levels", 1500)
        process_side_task.delay("Notify Shipping Partner", 3000)

        # NEW: The Poison Pill (This will fail 3 times and go to DLQ)
        process_side_task.delay("CRITICAL_FAIL_TASK", 1000)

        async_duration = (time.time() - start_time_async) * 1000
        self.stdout.write(f"[Log] Tasks queued! User wait time: {async_duration:.0f}ms.")

        # ---------------------------------------------------------
        # 3. COMPARISON & DLQ STATUS
        # ---------------------------------------------------------
        self.stdout.write("\n==================================================")
        self.stdout.write("3. RESULTS & MONITORING:")
        self.stdout.write("==================================================")
        self.stdout.write(f"Sync Wait:  ~{sync_duration:.0f}ms")
        self.stdout.write(f"Async Wait: ~{async_duration:.0f}ms")
        
        speedup = sync_duration / async_duration if async_duration > 0 else 0
        self.stdout.write(f"Performance Gain: {speedup:.0f}x faster!")
        self.stdout.write("\n[DLQ TEST]: Watch your Celery worker retry 'CRITICAL_FAIL_TASK' 3 times.")
        self.stdout.write("Then check 'dead_letter_queue' at http://localhost:15672/")