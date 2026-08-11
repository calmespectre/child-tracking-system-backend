from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import BeneficiaryViewSet, EmployeeActivityView
from .dashboard_views import DashboardView

router = DefaultRouter()
router.register(r"", BeneficiaryViewSet, basename="beneficiary")

urlpatterns = [
    path("", include(router.urls)),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("dashboard/", DashboardView.as_view(), name="dashboard", ),
    path("employee-activity/", EmployeeActivityView.as_view(),
         name="employee-activity", ),
]
