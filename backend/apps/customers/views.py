from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import CustomerProfile
from .serializers import CustomerLoginSerializer, CustomerRegistrationSerializer, CustomerProfileSerializer
from .services import login_customer


class CustomerLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tokens = login_customer(**serializer.validated_data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(tokens, status=200)


class CustomerRegistrationView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerRegistrationSerializer


class CustomerMeView(generics.RetrieveAPIView):
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        return CustomerProfile.objects.select_related('user').get(user=self.request.user)
