from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework.response import Response # استيراد لاستخدامه في الكاش
from django.core.cache import cache # استيراد كاش Redis للطلب السادس
from apps.cart.services import get_or_create_active_cart
from .models import Product
from .serializers import ProductSerializer
import time

class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    
    # الكويري الأصلي الفعلي لمشروعك
    queryset = Product.objects.select_related("category", "brand").prefetch_related("variants__inventory_record").filter(is_active=True)

    def list(self, request, *args, **kwargs):
        cache_key = "catalog:product_list:all"
        lock_key = "lock:catalog:product_list"
        
        start_time = time.time()
        
        # 1️⃣ محاولة جلب قائمة المنتجات من كاش Redis (Distributed Caching) تقليلاً للاستعلامات
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            print("\n🔒 [Lock Attempt] Request trying to acquire lock for Product List...")
            
            # 2️⃣ تطبيق الـ Distributed Lock لمنع مشكلة الـ Cache Stampede عند التزامن العالي
            with cache.lock(lock_key, timeout=10):
                # التثبت المزدوج (Double-Check) داخل القفل
                cached_data = cache.get(cache_key)
                
                if cached_data is None:
                    print("❌ [Cache Miss] Fetching from Database and optimizing queries...")
                    
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
