from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BeneficiaryViewSet,
    SupportLogViewSet,
    EmployeeActivityView,
    DashboardView,
)

router = DefaultRouter()

router.register(
    r"beneficiaries",
    BeneficiaryViewSet,
    basename="beneficiary",
)

router.register(
    r"support-logs",
    SupportLogViewSet,
    basename="support-log",
)

urlpatterns = [
    path(
        "dashboard/",
        DashboardView.as_view(),
        name="beneficiary-dashboard",
    ),
    path(
        "employee-activity/",
        EmployeeActivityView.as_view(),
        name="employee-activity",
    ),
    path(
        "",
        include(router.urls),
    ),
]
