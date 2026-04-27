from pathlib import Path
root = Path('/mnt/data/ecommerce_platform')
files = {
'README.md': '''# E-Commerce Platform Monorepo

Production-oriented starter monorepo for a customer mobile app, admin dashboard, and Django backend.

## What is included
- Django + DRF backend scaffold
- Modular monolith app layout
- PostgreSQL-ready settings
- JWT-ready REST API structure
- Customer auth separated from employee auth in domain/application design
- React admin dashboard starter
- Flutter mobile app starter
- Architecture docs

## Monorepo structure
```text
backend/      Django API
admin-web/    React admin dashboard starter
mobile-app/   Flutter mobile app starter
docs/         Architecture and roadmap
```

## Functional alignment with the SRS
This scaffold is designed around the uploaded SRS, including:
- customer mobile app and admin web panel
- OTP flows
- products with variants and selectable attributes
- cart, checkout, orders, reorder
- inventory tracking
- employee roles and permissions
- delivery and reporting hooks

## Notes
This is a **scaffolded foundation**, not a fully finished commercial product. It gives you the correct architecture, models, modules, and starter endpoints so implementation can continue cleanly.

## Backend quick start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Admin web quick start
```bash
cd admin-web
npm install
npm run dev
```

## Mobile app quick start
```bash
cd mobile-app
flutter pub get
flutter run
```
''',
'docs/architecture.md': '''# Architecture Summary

## Style
The backend is a **modular monolith**:
- one deployable backend service
- one primary PostgreSQL database
- clear module boundaries
- future extraction path if a module becomes large enough

## Backend modules
- users
- customers
- employees
- roles_permissions
- otp
- catalog
- inventory
- cart
- orders
- notifications
- common

## Auth strategy
### Customer auth
- phone-based registration/login
- OTP verification
- customer-facing JWT tokens

### Employee auth
- dashboard login
- staff role assignment
- permission-based access control
- separate API namespace and stricter policies

## Catalog strategy
- Product
- ProductOption
- OptionValue
- ProductVariant
- VariantOptionValue

## Inventory strategy
Inventory is stored at the **variant level**. This prevents overselling for combinations such as size/color/weight.

## Order strategy
- immutable order item price snapshot
- explicit status transitions
- inventory reservation and stock movements
- API versioning from day one
''',
'backend/requirements.txt': '''Django>=5.1,<5.3
 djangorestframework>=3.15,<3.16
 djangorestframework-simplejwt>=5.3,<5.4
 psycopg[binary]>=3.2,<3.3
 django-filter>=24.3,<24.4
 drf-spectacular>=0.27,<0.28
 python-dotenv>=1.0,<1.1
'''.replace(' ','',1),
'backend/.env.example': '''DEBUG=True
SECRET_KEY=change-me
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=ecommerce_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
''',
'backend/manage.py': '''#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
''',
'backend/config/settings.py': '''from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'django_filters',
    'apps.common',
    'apps.users',
    'apps.customers',
    'apps.employees',
    'apps.roles_permissions',
    'apps.otp',
    'apps.catalog',
    'apps.inventory',
    'apps.cart',
    'apps.orders',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ]},
    },
]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'ecommerce_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'users.User'
LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Damascus'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'E-Commerce Platform API',
    'DESCRIPTION': 'Customer and admin REST APIs',
    'VERSION': '1.0.0',
}
''',
'backend/config/urls.py': '''from django.contrib import admin
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
]
''',
'backend/config/wsgi.py': '''import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
''',
'backend/config/asgi.py': '''import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_asgi_application()
''',
'backend/apps/common/apps.py': '''from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
''',
'backend/apps/common/models.py': '''from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
''',
'backend/apps/users/apps.py': '''from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
''',
'backend/apps/users/models.py': '''from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.common.models import TimeStampedModel


class UserType(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    EMPLOYEE = 'employee', 'Employee'


class User(AbstractUser, TimeStampedModel):
    username = None
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True)
    user_type = models.CharField(max_length=20, choices=UserType.choices)
    is_phone_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return f'{self.phone_number} ({self.user_type})'
''',
'backend/apps/users/admin.py': '''from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ('id', 'phone_number', 'user_type', 'is_phone_verified', 'is_staff', 'is_active')
    ordering = ('id',)
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('user_type', 'is_phone_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'user_type', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
    search_fields = ('phone_number', 'first_name', 'last_name')
''',
'backend/apps/customers/apps.py': '''from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.customers'
''',
'backend/apps/customers/models.py': '''from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class AccountSource(models.TextChoices):
    SELF_REGISTERED = 'self_registered', 'Self Registered'
    ADMIN_CREATED = 'admin_created', 'Admin Created'
    IMPORTED = 'imported', 'Imported'


class CustomerProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    address = models.CharField(max_length=255, blank=True)
    province = models.CharField(max_length=100, blank=True)
    account_source = models.CharField(max_length=30, choices=AccountSource.choices, default=AccountSource.SELF_REGISTERED)
    must_set_password = models.BooleanField(default=False)
    first_login_pending = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'CustomerProfile<{self.user.phone_number}>'
''',
'backend/apps/customers/serializers.py': '''from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.users.models import UserType
from .models import CustomerProfile, AccountSource

User = get_user_model()


class CustomerRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)

    def create(self, validated_data):
        user = User.objects.create_user(
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', ''),
            user_type=UserType.CUSTOMER,
        )
        CustomerProfile.objects.create(user=user, account_source=AccountSource.SELF_REGISTERED)
        return user


class CustomerProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'address', 'province', 'account_source')
''',
'backend/apps/customers/views.py': '''from rest_framework import generics, permissions
from .models import CustomerProfile
from .serializers import CustomerRegistrationSerializer, CustomerProfileSerializer


class CustomerRegistrationView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerRegistrationSerializer


class CustomerMeView(generics.RetrieveAPIView):
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        return CustomerProfile.objects.select_related('user').get(user=self.request.user)
''',
'backend/apps/customers/urls.py': '''from django.urls import path
from .views import CustomerMeView, CustomerRegistrationView

urlpatterns = [
    path('auth/register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('me/', CustomerMeView.as_view(), name='customer-me'),
]
''',
'backend/apps/employees/apps.py': '''from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.employees'
''',
'backend/apps/employees/models.py': '''from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class EmployeeProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile')
    job_title = models.CharField(max_length=100)
    is_mfa_required = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f'EmployeeProfile<{self.user.phone_number}>'
''',
'backend/apps/employees/serializers.py': '''from rest_framework import serializers
from .models import EmployeeProfile


class EmployeeProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'job_title', 'is_mfa_required')
''',
'backend/apps/employees/views.py': '''from rest_framework import generics
from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer


class EmployeeMeView(generics.RetrieveAPIView):
    serializer_class = EmployeeProfileSerializer

    def get_object(self):
        return EmployeeProfile.objects.select_related('user').get(user=self.request.user)
''',
'backend/apps/employees/urls.py': '''from django.urls import path
from .views import EmployeeMeView

urlpatterns = [
    path('me/', EmployeeMeView.as_view(), name='employee-me'),
]
''',
'backend/apps/roles_permissions/apps.py': '''from django.apps import AppConfig


class RolesPermissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.roles_permissions'
''',
'backend/apps/roles_permissions/models.py': '''from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class Permission(TimeStampedModel):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)

    def __str__(self) -> str:
        return self.code


class Role(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')
    employees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='business_roles')

    def __str__(self) -> str:
        return self.name
''',
'backend/apps/otp/apps.py': '''from django.apps import AppConfig


class OtpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.otp'
''',
'backend/apps/otp/models.py': '''from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.common.models import TimeStampedModel


class OTPPurpose(models.TextChoices):
    REGISTER = 'register', 'Register'
    LOGIN = 'login', 'Login'
    FIRST_PASSWORD = 'first_password', 'First Password'
    ORDER_CONFIRMATION = 'order_confirmation', 'Order Confirmation'


class OTPChallenge(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otp_challenges')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=OTPPurpose.choices)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at
''',
'backend/apps/catalog/apps.py': '''from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.catalog'
''',
'backend/apps/catalog/models.py': '''from django.db import models
from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    def __str__(self) -> str:
        return self.name


class Brand(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products')
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class OptionType(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class OptionValue(TimeStampedModel):
    option_type = models.ForeignKey(OptionType, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)

    class Meta:
        unique_together = ('option_type', 'value')

    def __str__(self) -> str:
        return f'{self.option_type.name}: {self.value}'


class ProductOption(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_options')
    option_type = models.ForeignKey(OptionType, on_delete=models.PROTECT, related_name='product_options')
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('product', 'option_type')


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.sku


class VariantOptionValue(TimeStampedModel):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='variant_values')
    option_value = models.ForeignKey(OptionValue, on_delete=models.PROTECT, related_name='variant_values')

    class Meta:
        unique_together = ('variant', 'option_value')
''',
'backend/apps/catalog/serializers.py': '''from rest_framework import serializers
from .models import Brand, Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'parent')


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ('id', 'name')


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id', 'sku', 'price', 'is_active')


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'description', 'category', 'brand', 'is_active', 'variants')
''',
'backend/apps/catalog/views.py': '''from rest_framework import generics, permissions
from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related('category', 'brand').prefetch_related('variants').filter(is_active=True)


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related('category', 'brand').prefetch_related('variants').filter(is_active=True)
''',
'backend/apps/catalog/urls.py': '''from django.urls import path
from .views import ProductDetailView, ProductListView

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
''',
'backend/apps/inventory/apps.py': '''from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
''',
'backend/apps/inventory/models.py': '''from django.db import models
from apps.common.models import TimeStampedModel


class InventoryRecord(TimeStampedModel):
    variant = models.OneToOneField('catalog.ProductVariant', on_delete=models.CASCADE, related_name='inventory_record')
    quantity_available = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f'{self.variant.sku}: {self.quantity_available}'


class StockMovementType(models.TextChoices):
    RESERVE = 'reserve', 'Reserve'
    RELEASE = 'release', 'Release'
    SALE = 'sale', 'Sale'
    ADJUSTMENT = 'adjustment', 'Adjustment'


class StockMovement(TimeStampedModel):
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=30, choices=StockMovementType.choices)
    quantity = models.IntegerField()
    note = models.CharField(max_length=255, blank=True)
''',
'backend/apps/cart/apps.py': '''from django.apps import AppConfig


class CartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cart'
''',
'backend/apps/cart/models.py': '''from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class Cart(TimeStampedModel):
    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'variant')
''',
'backend/apps/cart/serializers.py': '''from rest_framework import serializers
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='variant.sku', read_only=True)
    price = serializers.DecimalField(source='variant.price', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ('id', 'variant', 'sku', 'price', 'quantity')


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ('id', 'items')
''',
'backend/apps/cart/views.py': '''from rest_framework import generics
from .models import Cart
from .serializers import CartSerializer


class CartDetailView(generics.RetrieveAPIView):
    serializer_class = CartSerializer

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(customer=self.request.user)
        return cart
''',
'backend/apps/cart/urls.py': '''from django.urls import path
from .views import CartDetailView

urlpatterns = [
    path('', CartDetailView.as_view(), name='cart-detail'),
]
''',
'backend/apps/orders/apps.py': '''from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'
''',
'backend/apps/orders/models.py': '''from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PREPARING = 'preparing', 'Preparing'
    GO_OUT = 'go_out', 'Go Out'
    CUSTOMER_RECEIVED = 'customer_received', 'Customer Received'
    COMPLETE = 'complete', 'Complete'
    CANCELLED = 'cancelled', 'Cancelled'


class Order(TimeStampedModel):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=30, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_address = models.CharField(max_length=255)
    province = models.CharField(max_length=100)


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'


class Payment(TimeStampedModel):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)


class Delivery(TimeStampedModel):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    province = models.CharField(max_length=100)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, default='pending')
''',
'backend/apps/orders/serializers.py': '''from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='variant.sku', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'sku', 'quantity', 'unit_price')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'status', 'total_amount', 'shipping_address', 'province', 'items', 'created_at')
''',
'backend/apps/orders/views.py': '''from rest_framework import generics
from .models import Order
from .serializers import OrderSerializer


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.prefetch_related('items__variant').filter(customer=self.request.user).order_by('-created_at')
''',
'backend/apps/orders/urls.py': '''from django.urls import path
from .views import OrderListView

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
]
''',
'backend/apps/notifications/apps.py': '''from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
''',
'backend/apps/notifications/models.py': '''from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
''',
'admin-web/package.json': '''{
  "name": "admin-web",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.1"
  }
}
''',
'admin-web/index.html': '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Admin Dashboard</title>
    <script type="module" src="/src/main.jsx"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
''',
'admin-web/src/main.jsx': '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
''',
'admin-web/src/app/App.jsx': '''export default function App() {
  const cards = [
    'Products & Variants',
    'Orders',
    'Inventory',
    'Customers',
    'Employees & Roles',
    'Reports',
  ]

  return (
    <main style={{fontFamily: 'sans-serif', padding: 24}}>
      <h1>Admin Dashboard Starter</h1>
      <p>React starter connected later to /api/v1/admin/* endpoints.</p>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginTop: 24}}>
        {cards.map((card) => (
          <section key={card} style={{border: '1px solid #ddd', borderRadius: 12, padding: 16}}>
            <h3>{card}</h3>
            <p>Feature module placeholder.</p>
          </section>
        ))}
      </div>
    </main>
  )
}
''',
'mobile-app/pubspec.yaml': '''name: mobile_app
description: Customer mobile app starter
publish_to: 'none'
version: 0.1.0+1

environment:
  sdk: '>=3.4.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.8

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^4.0.0

flutter:
  uses-material-design: true
''',
'mobile-app/lib/main.dart': '''import 'package:flutter/material.dart';

void main() {
  runApp(const CustomerApp());
}

class CustomerApp extends StatelessWidget {
  const CustomerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Customer App',
      theme: ThemeData(useMaterial3: true),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Customer App Starter')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          FeatureCard(title: 'Authentication', subtitle: 'OTP, registration, login'),
          FeatureCard(title: 'Catalog', subtitle: 'Products, variants, filters'),
          FeatureCard(title: 'Cart', subtitle: 'Session/local persistence'),
          FeatureCard(title: 'Orders', subtitle: 'History, reorder, tracking'),
          FeatureCard(title: 'Profile', subtitle: 'Address and account settings'),
        ],
      ),
    );
  }
}

class FeatureCard extends StatelessWidget {
  final String title;
  final String subtitle;

  const FeatureCard({super.key, required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(title: Text(title), subtitle: Text(subtitle)),
    );
  }
}
''',
}
for rel, content in files.items():
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
print(f'Created {len(files)} files')
