from django.urls import path

from .views import (
    RequestOTPView,
    VerifyOTPView,
    LogoutView,
    CreateUserView,
    ListUsersView,
    DeleteUserView,
    UpdateUserStatusView,
    UserSessionListView,
    CheckActiveStatusView,
    ResetUserPasswordView,
)


urlpatterns = [
    path(
        "request-otp/",
        RequestOTPView.as_view(),
        name="request-otp",
    ),
    path(
        "verify-otp/",
        VerifyOTPView.as_view(),
        name="verify-otp",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "create-user/",
        CreateUserView.as_view(),
        name="create-user",
    ),
    path(
        "users/",
        ListUsersView.as_view(),
        name="list-users",
    ),
    path(
        "users/<int:pk>/",
        DeleteUserView.as_view(),
        name="delete-user",
    ),
    path(
        "users/<int:pk>/status/",
        UpdateUserStatusView.as_view(),
        name="update-user-status",
    ),
    path(
        "user-sessions/",
        UserSessionListView.as_view(),
        name="user-sessions",
    ),
    path(
        "check-status/",
        CheckActiveStatusView.as_view(),
        name="check-status",
    ),
    path(
        "users/<int:pk>/reset-password/",
        ResetUserPasswordView.as_view(),
        name="reset-user-password",
    ),
]
