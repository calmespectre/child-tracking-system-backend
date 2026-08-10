from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from datetime import timedelta


class ActiveUserJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)

        if result is None:
            return None

        user, token = result

        if not user.is_active:
            raise AuthenticationFailed(
                "Your account has been deactivated. Please contact the administrator."
            )

        if user.last_activity and (
            timezone.now() - user.last_activity
        ) > timedelta(minutes=1440):
            raise AuthenticationFailed(
                "Session expired due to inactivity. Please log in again."
            )

        user.last_activity = timezone.now()
        user.save(update_fields=["last_activity"])

        return user, token
