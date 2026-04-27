from rest_framework import generics, permissions
from .models import CustomerProfile
from .serializers import CustomerRegistrationSerializer, CustomerProfileSerializer


class CustomerRegistrationView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerRegistrationSerializer


class CustomerMeView(generics.RetrieveAPIView):
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        return CustomerProfile.objects.select_related('user').get(user=self.request.user)
