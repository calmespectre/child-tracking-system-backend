from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import BeneficiaryViewSet

router = DefaultRouter()
router.register(r"", BeneficiaryViewSet, basename="beneficiary")

urlpatterns = [
    path("", include(router.urls)),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
