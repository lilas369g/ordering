from django.urls import path

from .views import ProductDetailView, ProductListView, storefront_product_list

app_name = "catalog"

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("store/", storefront_product_list, name="storefront-product-list"),
]
