from django.urls import path
from .views import EmployeeMeView

urlpatterns = [
    path('me/', EmployeeMeView.as_view(), name='employee-me'),
]
