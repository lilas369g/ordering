from django.conf import settings
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
