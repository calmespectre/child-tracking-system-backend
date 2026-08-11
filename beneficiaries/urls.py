from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BeneficiaryViewSet,
    EmployeeActivityView,
    DashboardView,
)

router = DefaultRouter()
router.register(
    r"",
    BeneficiaryViewSet,
    basename="beneficiary",
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
