from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BeneficiaryViewSet, GuardianViewSet

router = DefaultRouter()
router.register(r'beneficiaries', BeneficiaryViewSet, basename='beneficiary')
router.register(r'guardians', GuardianViewSet, basename='guardian')

urlpatterns = [
    path('', include(router.urls)),
    path('beneficiaries/import-guardians/',
         BeneficiaryViewSet.as_view({'post': 'import_guardians'}), name='import-guardians'),
]
