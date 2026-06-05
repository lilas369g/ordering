import os
import sys
import django
import threading
import time
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction, close_old_connections, connection
from django.db.models import F
from apps.catalog.models import Product, ProductVariant, Brand, Category
from apps.inventory.models import InventoryRecord

# Limit concurrent DB connections to prevent PostgreSQL overflow
CONN_SEMAPHORE = threading.Semaphore(30)

def setup_data(stock=50):
    # Reset inventory stock for each test run
    brand, _ = Brand.objects.get_or_create(name="TestBrand")
    category, _ = Category.objects.get_or_create(name="TestCategory")
    product, _ = Product.objects.get_or_create(name="TestProduct", brand=brand, category=category)
    variant, _ = ProductVariant.objects.get_or_create(product=product, sku="TEST-1", price=100)
    inv, created = InventoryRecord.objects.get_or_create(variant=variant, defaults={'quantity_available': stock})
    if not created:
        inv.quantity_available = stock
        inv.version = 0
        inv.save()
    return inv.id

def run_stress_test(inv_id, num_users, method_name, test_function):
    # Run concurrent stress test with threading.Barrier
    print(f"\n{'='*50}")
    print(f"  RUNNING: {method_name}")
    print(f"  {num_users} Concurrent Users | Stock=50")
    print(f"{'='*50}")

    results = {'success': 0, 'fail': 0, 'times': [], 'errors': []}
    lock = threading.Lock()
    barrier = threading.Barrier(num_users)

    def try_buy():
        # Wait for all threads then acquire semaphore before DB access
        close_old_connections()  # Reset stale connections before barrier
        barrier.wait()  # Synchronize all threads to start at exact same moment
        start_time = time.time()
        try:
            with CONN_SEMAPHORE:
                try:
                    test_function(inv_id)
                finally:
                    # Release this thread's DB connection while still holding the
                    # semaphore, so at most 30 connections exist at any moment
                    # (across all runs) and dead threads never leak connections.
                    connection.close()
            elapsed = time.time() - start_time
            with lock:
                results['success'] += 1
                results['times'].append(elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            with lock:
                results['fail'] += 1
                results['times'].append(elapsed)
                if len(results['errors']) < 3:
                    results['errors'].append(f"{type(e).__name__}: {e}")

    start_total = time.time()
    threads = [threading.Thread(target=try_buy) for _ in range(num_users)]
    for t in threads: t.start()
    for t in threads: t.join()
    total_time = time.time() - start_total

    inv = InventoryRecord.objects.get(id=inv_id)
    avg_time = sum(results['times']) / len(results['times']) if results['times'] else 0
    throughput = results['success'] / total_time if total_time > 0 else 0
    final_stock = inv.quantity_available

    print(f"  Successful Orders : {results['success']}")
    print(f"  Failed Orders     : {results['fail']}")
    print(f"  Final Stock       : {final_stock}")
    print(f"  Total Time        : {total_time:.4f} sec")
    print(f"  Avg Latency       : {avg_time:.4f} sec")
    print(f"  Throughput        : {throughput:.2f} orders/sec")
    if results['errors']:
        print(f"  Sample errors:")
        for err in results['errors']:
            print(f"    - {err}")

    return avg_time, throughput, results['success'], final_stock

def test_pessimistic(inv_id):
    # Strategy 1: Pessimistic Locking - select_for_update()
    with transaction.atomic():
        inv = InventoryRecord.objects.select_for_update().get(id=inv_id)
        if inv.quantity_available >= 1:
            inv.quantity_available -= 1
            inv.save(update_fields=['quantity_available'])
        else:
            raise Exception("Out of stock")

def test_optimistic(inv_id):
    # Strategy 2: Optimistic Locking - version field check with retry
    max_retries = 20
    for attempt in range(max_retries):
        inv = InventoryRecord.objects.get(id=inv_id)
        if inv.quantity_available < 1:
            raise Exception("Out of stock")
        updated = InventoryRecord.objects.filter(
            id=inv_id,
            version=inv.version
        ).update(
            quantity_available=F('quantity_available') - 1,
            version=F('version') + 1
        )
        if updated == 1:
            return
        time.sleep(0.005)
    raise Exception("Max retries exceeded")

def test_atomic(inv_id):
    # Strategy 3: Atomic F() Expression - single SQL UPDATE
    updated = InventoryRecord.objects.filter(
        id=inv_id,
        quantity_available__gte=1
    ).update(quantity_available=F('quantity_available') - 1)
    if updated == 0:
        raise Exception("Out of stock")

if __name__ == '__main__':
    # Request 9 & 10: 100 concurrent users stress test
    INV_ID = setup_data(stock=50)
    NUM_USERS = 100

    setup_data(stock=50)
    p_latency, p_throughput, p_success, p_stock = run_stress_test(INV_ID, NUM_USERS, "1. Pessimistic Locking", test_pessimistic)

    setup_data(stock=50)
    o_latency, o_throughput, o_success, o_stock = run_stress_test(INV_ID, NUM_USERS, "2. Optimistic Locking", test_optimistic)

    setup_data(stock=50)
    a_latency, a_throughput, a_success, a_stock = run_stress_test(INV_ID, NUM_USERS, "3. Atomic F() Expression (Smart)", test_atomic)

    print("\n" + "="*60)
    print("  FINAL BENCHMARKING COMPARISON (Request 9 & 10)")
    print("="*60)
    print(f"  Method               | Success | Avg Latency | Throughput")
    print(f"  ----------------------------------------------------------")
    print(f"  1. Pessimistic Lock  | {p_success:>7} | {p_latency:.4f} sec | {p_throughput:.2f} ord/sec")
    print(f"  2. Optimistic Lock   | {o_success:>7} | {o_latency:.4f} sec | {o_throughput:.2f} ord/sec")
    print(f"  3. Atomic F() (Smart)| {a_success:>7} | {a_latency:.4f} sec | {a_throughput:.2f} ord/sec")
    print(f"  ----------------------------------------------------------")

    strategies = [
        {
            "name": "Pessimistic Locking",
            "method": "select_for_update()",
            "successful_orders": p_success,
            "failed_orders": NUM_USERS - p_success,
            "avg_latency_ms": round(p_latency * 1000, 1),
            "throughput_orders_per_sec": round(p_throughput, 2),
            "data_integrity": p_success + p_stock == 50
        },
        {
            "name": "Optimistic Locking",
            "method": "version field check",
            "successful_orders": o_success,
            "failed_orders": NUM_USERS - o_success,
            "avg_latency_ms": round(o_latency * 1000, 1),
            "throughput_orders_per_sec": round(o_throughput, 2),
            "data_integrity": o_success + o_stock == 50
        },
        {
            "name": "Atomic F() Expression",
            "method": "F('quantity_available') - 1",
            "successful_orders": a_success,
            "failed_orders": NUM_USERS - a_success,
            "avg_latency_ms": round(a_latency * 1000, 1),
            "throughput_orders_per_sec": round(a_throughput, 2),
            "data_integrity": a_success + a_stock == 50
        }
    ]

    winner = max(strategies, key=lambda x: x['throughput_orders_per_sec'])['name']

    output = {
        "last_updated": datetime.now().isoformat(),
        "num_users": NUM_USERS,
        "stock_per_run": 50,
        "strategies": strategies,
        "winner": winner,
        "integrity_verified": all(s['data_integrity'] for s in strategies)
    }

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'concurrency_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Results saved to concurrency_results.json")
    print(f"🏆 Winner: {winner}")