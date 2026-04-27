from django.conf import settings
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
    customer_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
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
