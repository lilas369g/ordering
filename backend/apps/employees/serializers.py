from rest_framework import serializers
from .models import EmployeeProfile


class EmployeeProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'job_title', 'is_mfa_required')
