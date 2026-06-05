from django.urls import path
from .views import EmployeeMeView, performance_data, run_benchmark, benchmark_status

urlpatterns = [
    path('me/', EmployeeMeView.as_view(), name='employee-me'),
    path('performance-data/', performance_data, name='performance-data'),
    path('run-benchmark/<str:session>/', run_benchmark, name='run-benchmark'),
    path('benchmark-status/<str:session>/', benchmark_status, name='benchmark-status'),
]
