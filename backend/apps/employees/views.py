from rest_framework import generics
from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer


class EmployeeMeView(generics.RetrieveAPIView):
    serializer_class = EmployeeProfileSerializer

    def get_object(self):
        return EmployeeProfile.objects.select_related('user').get(user=self.request.user)
