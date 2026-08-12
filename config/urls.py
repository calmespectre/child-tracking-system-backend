from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/beneficiaries/", include("beneficiaries.urls")),
    path("api/support-logs/", include("beneficiaries.support_urls")),
]
