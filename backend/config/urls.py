from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/customer/', include('apps.customers.urls')),
    path('api/v1/admin/', include('apps.employees.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/cart/', include('apps.cart.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('', include('apps.storefront.urls')),
]

