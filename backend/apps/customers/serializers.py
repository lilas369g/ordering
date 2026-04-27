from django.contrib.auth import get_user_model
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
