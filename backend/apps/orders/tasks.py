import time
from celery import current_app, shared_task
from celery.exceptions import Reject

@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
)
def process_side_task(self, task_name, duration_ms):
    delivery_info = getattr(self.request, 'delivery_info', None) or {}
    headers = getattr(self.request, 'headers', None) or {}

    if delivery_info.get('routing_key') == 'dead_letter_queue':
        print(
            f"[DLQ INSPECTOR] '{task_name}' is in quarantine. "
            f"Original task id: {headers.get('x-task-id', 'unknown')}"
        )
        return f"Dead-lettered: {task_name}"

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

                current_app.send_task(
                    self.name,
                    args=self.request.args,
                    kwargs=self.request.kwargs,
                    queue='dead_letter_queue',
                    headers={
                        'x-death-reason': str(exc),
                        'x-original-queue': 'celery',
                        'x-retry-count': str(self.max_retries),
                        'x-task-id': self.request.id,
                    },
                )
                return f"Dead-lettered: {task_name}"
            
            # 2. If not at the limit, retry as normal
            raise self.retry(exc=exc, countdown=5)

    # Standard success path
    print(f"Working on: {task_name}")
    time.sleep(duration_ms / 1000)
    return f"Finished {task_name}"