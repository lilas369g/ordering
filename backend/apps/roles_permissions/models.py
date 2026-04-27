from django.conf import settings
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
