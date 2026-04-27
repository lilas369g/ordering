from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class EmployeeProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile')
    job_title = models.CharField(max_length=100)
    is_mfa_required = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f'EmployeeProfile<{self.user.phone_number}>'
