from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer
from .services import CheckoutError, checkout_cart


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.prefetch_related('items__variant').filter(customer=self.request.user).order_by('-created_at')


class CheckoutView(APIView):
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = checkout_cart(request.user, **serializer.validated_data)
        except CheckoutError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "تم الطلب بنجاح",
                "order_id": order.id,
            },
            status=status.HTTP_201_CREATED,
        )
  