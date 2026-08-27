import os
import secrets
import string
import requests
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from .models import OTP, UserSession, UserPasswordHistory, ActivityLog
from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    CreateUserSerializer,
    UserSerializer,
    UserSessionSerializer,
    ActivityLogSerializer,
)
from .permissions import IsAdmin

User = get_user_model()
OTP_INTERVAL_HOURS = 12
SESSION_TIMEOUT_HOURS = 12
PASSWORD_HISTORY_COUNT = 5


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        return x_real_ip.strip()
    return request.META.get("REMOTE_ADDR", "").strip()


def get_user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")


def log_activity(user, action, request, details=None):
    if details is None:
        details = {}
    ActivityLog.objects.create(
        user=user,
        action=action,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        details=details,
    )


def send_brevo_email(to_emails, subject, text_content, html_content=None):
    # ... same as before, unchanged ...
    pass  # Keep existing implementation


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["name"] = user.get_full_name() or user.username
    refresh["email"] = user.email
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def otp_recently_verified(user):
    if not user.last_password_auth:
        return False
    elapsed = timezone.now() - user.last_password_auth
    return elapsed < timezone.timedelta(hours=OTP_INTERVAL_HOURS)


def create_login_response(user, request):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    now = timezone.now()
    UserSession.objects.create(
        user=user, action="LOGIN", ip_address=ip, user_agent=ua)
    user.last_ip = ip
    user.last_activity = now
    user.save(update_fields=["last_ip", "last_activity"])
    tokens = get_tokens_for_user(user)
    log_activity(user, 'LOGIN', request)
    # ... email notifications (existing code) ...
    return {**tokens, "user": {"name": user.get_full_name() or user.username, "email": user.email, "role": user.role}}


class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # ... same as before ...
        pass


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # ... same as before, but after successful login, we log activity inside create_login_response
        pass


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = get_client_ip(request)
        ua = get_user_agent(request)
        UserSession.objects.create(
            user=request.user, action="LOGOUT", ip_address=ip, user_agent=ua)
        request.user.last_activity = None
        request.user.save(update_fields=["last_activity"])
        log_activity(request.user, 'LOGOUT', request)
        # Blacklist the refresh token if present
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = request.data.get("password", "")
        if not password:
            alphabet = string.ascii_letters + string.digits
            generated_password = "".join(
                secrets.choice(alphabet) for _ in range(12))
            user = User.objects.create_user(
                email=serializer.validated_data["email"],
                role=serializer.validated_data["role"],
                username=serializer.validated_data.get("username", ""),
                password=generated_password
            )
            # Save initial password in history
            UserPasswordHistory.objects.create(
                user=user, password_hash=make_password(generated_password))
            log_activity(request.user, 'CREATE_USER', request, {
                         "created_user": user.email, "generated": True})
            return Response({
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "generated_password": generated_password
            }, status=status.HTTP_201_CREATED)
        user = serializer.save()
        UserPasswordHistory.objects.create(
            user=user, password_hash=make_password(password))
        log_activity(request.user, 'CREATE_USER', request, {
                     "created_user": user.email, "generated": False})
        return Response({"id": user.id, "email": user.email, "role": user.role}, status=status.HTTP_201_CREATED)


class ListUsersView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.all().order_by("email")
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if user_obj == request.user:
            return Response({"detail": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST)
        email = user_obj.email
        user_obj.delete()
        log_activity(request.user, 'DELETE_USER',
                     request, {"deleted_user": email})
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateUserStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if user_obj == request.user:
            return Response({"detail": "You cannot change your own status."}, status=status.HTTP_400_BAD_REQUEST)
        if "is_active" not in request.data:
            return Response({"detail": "is_active field is required."}, status=status.HTTP_400_BAD_REQUEST)
        is_active = request.data.get("is_active")
        if isinstance(is_active, str):
            is_active = is_active.lower() == "true"
        user_obj.is_active = bool(is_active)
        user_obj.save(update_fields=["is_active"])
        log_activity(request.user, 'UPDATE_USER_STATUS', request, {
                     "user": user_obj.email, "new_status": is_active})
        serializer = UserSerializer(user_obj)
        return Response(serializer.data)


class UserSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        email = request.query_params.get("email", "").strip()
        if not email:
            return Response({"detail": "Email query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_obj = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        sessions = UserSession.objects.filter(
            user=user_obj).select_related("user").order_by("-timestamp")
        serializer = UserSessionSerializer(sessions, many=True)
        return Response(serializer.data)


class CheckActiveStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"is_active": request.user.is_active, "email": request.user.email})


class ResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        new_password = request.data.get("password", "")
        if not new_password:
            alphabet = string.ascii_letters + string.digits
            new_password = "".join(secrets.choice(alphabet) for _ in range(12))

        # Check password history (last 5 passwords)
        recent_hashes = UserPasswordHistory.objects.filter(
            user=user_obj)[:PASSWORD_HISTORY_COUNT]
        for entry in recent_hashes:
            if check_password(new_password, entry.password_hash):
                return Response({
                    "detail": f"You cannot reuse your last {PASSWORD_HISTORY_COUNT} passwords."
                }, status=status.HTTP_400_BAD_REQUEST)

        user_obj.set_password(new_password)
        user_obj.save(update_fields=["password"])
        # Save new password hash to history
        UserPasswordHistory.objects.create(
            user=user_obj, password_hash=make_password(new_password))

        # Log activity
        log_activity(request.user, 'RESET_PASSWORD', request,
                     {"target_user": user_obj.email})

        # Optionally logout all devices
        logout_all = request.data.get("logout_all_devices", False)
        if logout_all:
            # Blacklist all outstanding refresh tokens for this user
            outstanding = OutstandingToken.objects.filter(user=user_obj)
            for token in outstanding:
                try:
                    BlacklistedToken.objects.get_or_create(token=token)
                except Exception:
                    pass
            # Also clear last activity to force re-login
            user_obj.last_activity = None
            user_obj.save(update_fields=["last_activity"])

        return Response({
            "email": user_obj.email,
            "new_password": new_password,
            "logout_all_devices": logout_all
        }, status=status.HTTP_200_OK)


class ActivityLogListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        email = request.query_params.get("email")
        if email:
            try:
                user_obj = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
            logs = ActivityLog.objects.filter(
                user=user_obj).order_by("-timestamp")
        else:
            logs = ActivityLog.objects.all().order_by("-timestamp")
        # Limit to last 500 for performance
        logs = logs[:500]
        serializer = ActivityLogSerializer(logs, many=True)
        return Response(serializer.data)
