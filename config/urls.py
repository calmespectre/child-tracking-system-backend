from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from beneficiaries.views import (
    SupportLogViewSet,
)

support_router = DefaultRouter()
support_router.register(
    r"support-logs",
    SupportLogViewSet,
    basename="root-support-log",
)

urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),
    path(
        "api/auth/",
        include("accounts.urls"),
    ),
    path(
        "api/beneficiaries/",
        include("beneficiaries.urls"),
    ),
    path(
        "api/",
        include(support_router.urls),
    ),
]
