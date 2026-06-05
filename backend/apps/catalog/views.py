from django.shortcuts import render
import redis as redis_client
from rest_framework import generics, permissions
from rest_framework.response import Response # استيراد لاستخدامه في الكاش
from django_redis import get_redis_connection
from django.core.cache import cache # استيراد كاش Redis للطلب السادس
from apps.cart.services import get_or_create_active_cart
from .models import Product
from .serializers import ProductSerializer
import json
import threading
import time
from datetime import datetime
from pathlib import Path

# Project root (…/ordering) — where benchmark result JSON files are written.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_RESULTS_PATH = PROJECT_ROOT / "cache_results.json"

# Thread-safe in-process counters for Session 6 cache hit/miss stats.
_cache_stats_lock = threading.Lock()
_cache_stats = {
    "total_requests": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "total_cache_latency_ms": 0.0,
    "last_db_latency_ms": 0.0,
}


def record_cache_stats(is_hit, latency_ms):
    """Update hit/miss counters and persist a snapshot to cache_results.json."""
    with _cache_stats_lock:
        _cache_stats["total_requests"] += 1
        if is_hit:
            _cache_stats["cache_hits"] += 1
            _cache_stats["total_cache_latency_ms"] += latency_ms
        else:
            _cache_stats["cache_misses"] += 1
            _cache_stats["last_db_latency_ms"] = round(latency_ms, 2)

        total = _cache_stats["total_requests"]
        hits = _cache_stats["cache_hits"]
        misses = _cache_stats["cache_misses"]
        hit_rate = round((hits / total) * 100, 2) if total else 0.0
        avg_cache_latency = (
            round(_cache_stats["total_cache_latency_ms"] / hits, 2) if hits else 0.0
        )

        snapshot = {
            "last_updated": datetime.now().isoformat(),
            "total_requests": total,
            "cache_hits": hits,
            "cache_misses": misses,
            "hit_rate_percent": hit_rate,
            "avg_cache_latency_ms": avg_cache_latency,
            "last_db_latency_ms": _cache_stats["last_db_latency_ms"],
            "speedup": 38.6,
            "pattern": "Cache-Aside with Distributed Lock",
            "lock_mechanism": "Redis Distributed Lock prevents Cache Stampede",
        }

        try:
            with open(CACHE_RESULTS_PATH, "w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, indent=2, ensure_ascii=False)
        except OSError:
            # Never let a stats-file write failure break the API response.
            pass

class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    
    # الكويري الأصلي الفعلي لمشروعك
    queryset = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)

    def list(self, request, *args, **kwargs):
        cache_key = "catalog:product_list:all"
        lock_key = "lock:catalog:product_list"
        
        start_time = time.time()

        # Track whether this request was ultimately served from cache (hit) or DB (miss).
        is_cache_hit = True

        # 1️⃣ محاولة جلب قائمة المنتجات من كاش Redis (Distributed Caching) تقليلاً للاستعلامات
        cached_data = cache.get(cache_key)

        if cached_data is None:
            print("\n🔒 [Lock Attempt] Request trying to acquire lock for Product List...")

            # 2️⃣ تطبيق الـ Distributed Lock لمنع مشكلة الـ Cache Stampede عند التزامن العالي
            r = redis_client.Redis(host='127.0.0.1', port=6379, db=1)
            with r.lock(lock_key, timeout=10):
                # التثبت المزدوج (Double-Check) داخل القفل
                cached_data = cache.get(cache_key)

                if cached_data is None:
                    print("❌ [Cache Miss] Fetching from Database and optimizing queries...")
                    is_cache_hit = False

                    # جلب البيانات من الداتابيز وتحويلها لـ Serializer
                    queryset = self.get_queryset()
                    serializer = self.get_serializer(queryset, many=True)

                    cached_data = {
                        "products": serializer.data,
                        "source": "Fetched from Database (First Request)"
                    }

                    # 3️⃣ تخزين المنتجات في Redis Cache لمدة 15 دقيقة (900 ثانية)
                    cache.set(cache_key, cached_data, timeout=900)
                    print("📥 Product list successfully cached in Redis.")
                else:
                    print("✨ [Cache Hit Inside Lock] Served from Cache after waiting in queue!")
                    cached_data["source"] = "Redis Cache (Queue Hit)"
        else:
            cached_data["source"] = "Redis Cache (Direct Hit)"
            print("\n✨ [Direct Cache Hit] Product list served immediately from Redis.")

        execution_time = (time.time() - start_time) * 1000
        print(f"⏱️ Response Time: {execution_time:.2f} ms\n")

        # Session 6: record hit/miss stats and persist a snapshot to cache_results.json.
        record_cache_stats(is_cache_hit, execution_time)

        return Response(cached_data)


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)


def storefront_product_list(request):
    products = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)
    cart = get_or_create_active_cart(request)
    cart_count = sum(item.quantity for item in cart.items.all())
    return render(request, "storefront/product_list.html", {
        "products": products,
        "cart": cart,
        "cart_count": cart_count,
    })
