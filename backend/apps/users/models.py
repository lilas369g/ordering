from django.contrib.auth.models import AbstractUser
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
