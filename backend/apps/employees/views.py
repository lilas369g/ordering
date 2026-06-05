import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from django.core.management import call_command
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer

# Project root (…/ordering) — where benchmark result JSON files live.
# views.py -> employees -> apps -> backend -> ordering  (4 parents).
BASE_DIR = Path(__file__).resolve().parents[3]

# Track running benchmarks so we don't launch the same one twice.
_running = {}
_running_lock = threading.Lock()


class EmployeeMeView(generics.RetrieveAPIView):
    serializer_class = EmployeeProfileSerializer

    def get_object(self):
        return EmployeeProfile.objects.select_related('user').get(user=self.request.user)


@api_view(['GET'])
@permission_classes([AllowAny])
def performance_data(request):
    result = {}
    files = {
        "algorithms": "all_algorithms_results.json",
        "concurrency": "concurrency_results.json",
        "batch_etl": "batch_etl_results.json",
        "cache": "cache_results.json",
        "thread_pool": "thread_pool_results.json",
        "checkout_race": "checkout_race_results.json",
        "testing_summary": "testing_summary_results.json",
    }
    for key, filename in files.items():
        path = BASE_DIR / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                result[key] = json.load(f)
        else:
            result[key] = None
    return Response(result)


@api_view(['POST'])
@permission_classes([AllowAny])
def run_benchmark(request, session):
    with _running_lock:
        if _running.get(session):
            return Response({"status": "already_running"}, status=409)
        _running[session] = True

    def _run():
        # Buffer command output so emoji/✓ writes don't crash on Windows cp1252.
        out, err = io.StringIO(), io.StringIO()
        try:
            if session == "thread_pool":
                call_command('simulate_external_service_thread_pool', stdout=out, stderr=err)
            elif session == "batch_etl":
                # Reset is best-effort: a fresh date may have nothing to reset.
                try:
                    call_command('reset_daily_sales_processing', '2026-05-04', stdout=out, stderr=err)
                except Exception:
                    pass
                call_command('seed_batch_demo_orders', stdout=out, stderr=err)
                call_command(
                    'process_daily_sales_batch', '2026-05-04', compare=True,
                    stdout=out, stderr=err,
                )
            elif session == "checkout_race":
                call_command('simulate_checkout_race', stdout=out, stderr=err)
            elif session == "concurrency":
                subprocess.run(
                    [sys.executable, 'test_concurrency.py'],
                    cwd=str(BASE_DIR / 'backend'),
                    env={**os.environ, 'PYTHONUTF8': '1'},
                )
        finally:
            with _running_lock:
                _running[session] = False

    threading.Thread(target=_run, daemon=True).start()
    return Response({"status": "started", "session": session})


@api_view(['GET'])
@permission_classes([AllowAny])
def benchmark_status(request, session):
    with _running_lock:
        running = _running.get(session, False)
    return Response({"session": session, "running": running})
