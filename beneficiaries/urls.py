from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    BeneficiaryViewSet, GuardianViewSet,
    DashboardView, EmployeeActivityView
)

router = DefaultRouter()
router.register(r'', BeneficiaryViewSet, basename='beneficiary')
router.register(r'guardians', GuardianViewSet, basename='guardian')

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='beneficiary-dashboard'),
    path('employee-activity/', EmployeeActivityView.as_view(),
         name='employee-activity'),
    path('', include(router.urls)),
]
