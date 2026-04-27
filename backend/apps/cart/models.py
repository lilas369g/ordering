from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class CartStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ORDERED = "ordered", "Ordered"
    EXPIRED = "expired", "Expired"


def default_cart_expiry():
    return timezone.now() + timedelta(days=3)


class Cart(TimeStampedModel):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=CartStatus.choices, default=CartStatus.ACTIVE)
    expires_at = models.DateTimeField(default=default_cart_expiry)

    def __str__(self):
        return f"Cart #{self.pk}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("cart", "variant")
