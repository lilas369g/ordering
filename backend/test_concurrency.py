import os
import sys
import django
import threading
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.db.models import F
from apps.catalog.models import Product, ProductVariant, Brand, Category
from apps.inventory.models import InventoryRecord

def setup_data(stock=50):
    """تجهيز الداتا وإعادة ضبط المخزون"""
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
    print(f"\n{'='*50}")
    print(f"  RUNNING: {method_name}")
    print(f"  {num_users} Concurrent Users | Stock=50")
    print(f"{'='*50}")

    results = {'success': 0, 'fail': 0, 'times': []}
    lock = threading.Lock()

    def try_buy():
        start_time = time.time()
        try:
            test_function(inv_id)
            elapsed = time.time() - start_time
            with lock:
                results['success'] += 1
                results['times'].append(elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            with lock:
                results['fail'] += 1
                results['times'].append(elapsed)

    # إطلاق الـ Threads
    start_total = time.time()
    threads = [threading.Thread(target=try_buy) for _ in range(num_users)]
    for t in threads: t.start()
    for t in threads: t.join()
    total_time = time.time() - start_total

    # حساب الأرقام (Benchmarking)
    inv = InventoryRecord.objects.get(id=inv_id)
    avg_time = sum(results['times']) / len(results['times']) if results['times'] else 0
    throughput = results['success'] / total_time if total_time > 0 else 0

    print(f"  Successful Orders : {results['success']}")
    print(f"  Failed Orders     : {results['fail']}")
    print(f"  Final Stock       : {inv.quantity_available}")
    print(f"  Total Time        : {total_time:.4f} sec")
    print(f"  Avg Latency       : {avg_time:.4f} sec")
    print(f"  Throughput        : {throughput:.2f} orders/sec")

    return avg_time, throughput, results['success']

# --- تعريف الطرق الثلاثة يلي بنختبرها ---

def test_pessimistic(inv_id):
    """الطريقة 1: Pessimistic Locking (قفل الصف)"""
    with transaction.atomic():
        inv = InventoryRecord.objects.select_for_update().get(id=inv_id)
        if inv.quantity_available >= 1:
            inv.quantity_available -= 1
            inv.save(update_fields=['quantity_available'])
        else:
            raise Exception("Out of stock")

def test_optimistic(inv_id):
    """الطريقة 2: Optimistic Locking (فحص الـ version)"""
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
    if updated == 0:
        raise Exception("Optimistic Conflict! Retry needed")

def test_atomic(inv_id):
    """الطريقة 3: Atomic F() Expression (بدون أقفال - الحل الذكي)"""
    updated = InventoryRecord.objects.filter(
        id=inv_id,
        quantity_available__gte=1
    ).update(quantity_available=F('quantity_available') - 1)
    
    if updated == 0:
        raise Exception("Out of stock")

if __name__ == '__main__':
    INV_ID = setup_data(stock=50)
    NUM_USERS = 100 # طلب 9: 100 متزامن

    # 1. اختبار Pessimistic
    setup_data(stock=50)
    p_latency, p_throughput, p_success = run_stress_test(INV_ID, NUM_USERS, "1. Pessimistic Locking", test_pessimistic)

    # 2. اختبار Optimistic
    setup_data(stock=50)
    o_latency, o_throughput, o_success = run_stress_test(INV_ID, NUM_USERS, "2. Optimistic Locking", test_optimistic)

    # 3. اختبار Atomic F()
    setup_data(stock=50)
    a_latency, a_throughput, a_success = run_stress_test(INV_ID, NUM_USERS, "3. Atomic F() Expression (Smart)", test_atomic)

    # --- جدول المقارنة النهائي (الطلب 9 و 10) ---
    print("\n" + "="*60)
    print("  FINAL BENCHMARKING COMPARISON (Request 9 & 10)")
    print("="*60)
    print(f"  Method               | Success | Avg Latency | Throughput")
    print(f"  ----------------------------------------------------------")
    print(f"  1. Pessimistic Lock  | {p_success:>7} | {p_latency:.4f} sec | {p_throughput:.2f} ord/sec")
    print(f"  2. Optimistic Lock   | {o_success:>7} | {o_latency:.4f} sec | {o_throughput:.2f} ord/sec")
    print(f"  3. Atomic F() (Smart)| {a_success:>7} | {a_latency:.4f} sec | {a_throughput:.2f} ord/sec")
    print(f"  ----------------------------------------------------------")
    print("  NOTE: Results depend on the Database Engine (SQLite vs PostgreSQL).")
    print("  PostgreSQL will show much higher Throughput for Atomic & correct Pessimistic behavior.")