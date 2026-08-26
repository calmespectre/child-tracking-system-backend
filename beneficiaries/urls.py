from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import BeneficiaryViewSet, GuardianViewSet

router = DefaultRouter()
router.register(r'', BeneficiaryViewSet, basename='beneficiary')
router.register(r'guardians', GuardianViewSet, basename='guardian')

urlpatterns = [
    path('', include(router.urls)),
]
