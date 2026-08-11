from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BeneficiaryViewSet,
    NoteViewSet,
    DocumentViewSet,
    SupportLogViewSet,
    EmployeeActivityView,
    DashboardSummaryView,
)

router = DefaultRouter()

router.register(
    "beneficiaries",
    BeneficiaryViewSet,
    basename="beneficiary",
)

router.register(
    "notes",
    NoteViewSet,
    basename="note",
)

router.register(
    "documents",
    DocumentViewSet,
    basename="document",
)

router.register(
    "support-logs",
    SupportLogViewSet,
    basename="support-log",
)

urlpatterns = [
    path(
        "dashboard/",
        DashboardSummaryView.as_view(),
        name="dashboard",
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
