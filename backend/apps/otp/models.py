from django.conf import settings
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
