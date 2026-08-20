from datetime import timedelta

from django.utils import timezone

from rest_framework.exceptions import AuthenticationFailed

from rest_framework_simplejwt.authentication import (
    JWTAuthentication,
)


SESSION_TIMEOUT = timedelta(
    hours=5
)


class ActiveUserJWTAuthentication(
    JWTAuthentication
):
    def authenticate(self, request):
        result = super().authenticate(
            request
        )

        if result is None:
            return None

        user, token = result

        if not user.is_active:
            raise AuthenticationFailed(
                "Your account has been deactivated. "
                "Please contact the administrator."
            )

        now = timezone.now()

        if user.last_activity:
            inactive_for = (
                now - user.last_activity
            )

            if inactive_for > SESSION_TIMEOUT:
                raise AuthenticationFailed(
                    "Your session expired after "
                    "5 hours of inactivity. "
                    "Please log in again."
                )

        user.last_activity = now

        user.save(
            update_fields=[
                "last_activity"
            ]
        )

        return user, token
