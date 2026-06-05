import os
import sys
import time
import threading
import statistics

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'])
    import requests

BASE_URL = 'http://localhost/api/v1'
PASSWORD = 'Test@1234'
FAST_THREADS = 30
FAST_REQUESTS_PER_THREAD = 20
SLOW_THREADS = 10


def login_users():
    tokens = []
    for i in range(1, 11):
        phone = f'091100000{i}'
        resp = requests.post(
            f'{BASE_URL}/customer/auth/login/',
            json={'phone_number': phone, 'password': PASSWORD},
            timeout=10,
        )
        resp.raise_for_status()
        tokens.append(resp.json()['access'])
        print(f'Logged in: {phone}')
    return tokens


def get_first_variant_id(token):
    resp = requests.get(
        f'{BASE_URL}/catalog/products/',
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    products = data if isinstance(data, list) else data.get('results', [])
    for product in products:
        variants = product.get('variants', [])
        if variants:
            return variants[0]['id']
    raise RuntimeError('No variants found in catalog')


def add_cart_items(tokens, variant_id):
    for token in tokens:
        resp = requests.post(
            f'{BASE_URL}/cart/add/',
            json={'variant_id': variant_id, 'quantity': 1},
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f'Cart add warning: {resp.status_code} {resp.text[:100]}')


def run_fast_worker(barrier, results):
    barrier.wait()
    local = []
    for _ in range(FAST_REQUESTS_PER_THREAD):
        t0 = time.perf_counter()
        try:
            requests.get(f'{BASE_URL}/catalog/products/', timeout=10)
        except Exception:
            pass
        local.append(time.perf_counter() - t0)
    results.extend(local)


def run_slow_worker(barrier, token, results):
    barrier.wait()
    t0 = time.perf_counter()
    try:
        requests.post(
            f'{BASE_URL}/orders/checkout/',
            json={
                'customer_name': 'Test User',
                'phone_number': '0911000001',
                'shipping_address': 'Damascus',
                'province': 'Damascus',
            },
            headers={'Authorization': f'Bearer {token}'},
            timeout=30,
        )
    except Exception:
        pass
    results.append(time.perf_counter() - t0)


def percentile(data, p):
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def print_stats(label, times):
    if not times:
        print(f'{label}: no data')
        return
    print(f'\n  {label}:')
    print(f'    Count : {len(times)}')
    print(f'    Mean  : {statistics.mean(times)*1000:.1f} ms')
    print(f'    Min   : {min(times)*1000:.1f} ms')
    print(f'    Max   : {max(times)*1000:.1f} ms')
    print(f'    p95   : {percentile(times, 95)*1000:.1f} ms')


def run_benchmark(label, tokens):
    print(f'\n{"="*60}')
    print(f'  {label}')
    print(f'{"="*60}')

    fast_results = []
    slow_results = []
    barrier = threading.Barrier(FAST_THREADS + SLOW_THREADS)

    threads = []
    for _ in range(FAST_THREADS):
        t = threading.Thread(target=run_fast_worker, args=(barrier, fast_results))
        threads.append(t)

    for i in range(SLOW_THREADS):
        token = tokens[i % len(tokens)]
        t = threading.Thread(target=run_slow_worker, args=(barrier, token, slow_results))
        threads.append(t)

    overall_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_time = time.perf_counter() - overall_start

    print_stats('Group A — catalog GET (fast)', fast_results)
    print_stats('Group B — checkout POST (slow)', slow_results)
    print(f'\n  Total wall time: {total_time:.2f}s')
    print(f'  Note: per-worker request counts not visible from client side.')


def main():
    print('Logging in 10 benchmark users...')
    tokens = login_users()

    print('\nFetching first variant ID...')
    variant_id = get_first_variant_id(tokens[0])
    print(f'Using variant_id={variant_id}')

    print('\nAdding cart items for all users...')
    add_cart_items(tokens, variant_id)

    run_benchmark('Testing with current algorithm (check nginx.conf)', tokens)
    run_benchmark('Testing with current algorithm (check nginx.conf) — run 2', tokens)


if __name__ == '__main__':
    main()
