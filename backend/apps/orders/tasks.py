import time
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from celery.exceptions import Reject

@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
)
def process_side_task(self, task_name, duration_ms):
    if "FAIL" in task_name.upper():
        current_attempt = self.request.retries + 1
        print(f"!!! Intentional Failure: {task_name} (Attempt {current_attempt}/4)")
        
        try:
            # Your simulated business logic failure
            raise ValueError("Simulated system crash for DLQ testing.")
            
        except Exception as exc:
            # 1. Check if we have exhausted all retries (Attempt 4)
            if self.request.retries >= self.max_retries:
                print(f"!!! Final attempt failed. Sending to DLQ...")
                raise Reject(exc, requeue=False)  # This MUST be reached
            
            # 2. If not at the limit, retry as normal
            raise self.retry(exc=exc, countdown=5)

    # Standard success path
    print(f"Working on: {task_name}")
    time.sleep(duration_ms / 1000)
    return f"Finished {task_name}"