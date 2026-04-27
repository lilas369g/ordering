from django.urls import path
from .views import CustomerMeView, CustomerRegistrationView

urlpatterns = [
    path('auth/register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('me/', CustomerMeView.as_view(), name='customer-me'),
]
