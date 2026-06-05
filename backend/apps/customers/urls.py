from django.urls import path
from .views import CustomerLoginView, CustomerMeView, CustomerRegistrationView

urlpatterns = [
    path('auth/login/', CustomerLoginView.as_view(), name='customer-login'),
    path('auth/register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('me/', CustomerMeView.as_view(), name='customer-me'),
]
