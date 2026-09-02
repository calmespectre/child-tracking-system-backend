from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/disbursements/", include("disbursements.urls")),
    path("api/beneficiaries/", include("beneficiaries.urls")),
    path("api/", include("chat.urls")),
]
