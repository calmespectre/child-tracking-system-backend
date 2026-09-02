import os
import secrets
import string
import requests
from django.db import IntegrityError
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from .models import OTP, UserSession, UserPasswordHistory, ActivityLog, PublicKey
from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    CreateUserSerializer,
    UserSerializer,
    UserProfileSerializer,
    UserSessionSerializer,
    ActivityLogSerializer,
    PublicKeySerializer,
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
    api_key = os.environ.get("BREVO_API_KEY")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL")
    sender_name = os.environ.get(
        "BREVO_SENDER_NAME", "MKCDP Child Tracking System")
    if not api_key:
        raise ValueError("BREVO_API_KEY is not configured.")
    if not sender_email:
        raise ValueError("BREVO_SENDER_EMAIL is not configured.")
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": email} for email in to_emails],
        "subject": subject,
        "textContent": text_content,
    }
    if html_content:
        payload["htmlContent"] = html_content
    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"accept": "application/json", "api-key": api_key,
                 "content-type": "application/json"},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


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
    login_time = now.strftime("%d-%m-%Y %H:%M:%S")
    device_info = ua or "Unknown device"
    try:
        send_brevo_email(
            to_emails=user.email,
            subject="MKCDP Login Notification",
            text_content=(
                f"Dear {user.get_full_name() or user.username},\n\n"
                "A login to your MKCDP Child-Tracking-System account was detected.\n\n"
                f"Email: {user.email}\nTime: {login_time}\nDevice: {device_info}\nIP Address: {ip}\n\n"
                "If this was not you, please contact the administrator immediately."
            ),
            html_content=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:40px auto;padding:30px;border:1px solid #e5e5e5;border-radius:12px;">
                    <h2>MKCDP Login Notification</h2>
                    <p>Dear {user.get_full_name() or user.username},</p>
                    <p>A login to your MKCDP Child-Tracking-System account was detected.</p>
                    <p><strong>Email:</strong> {user.email}</p>
                    <p><strong>Time:</strong> {login_time}</p>
                    <p><strong>IP Address:</strong> {ip}</p>
                    <p>If this was not you, please contact the administrator immediately.</p>
                </div>
            """,
        )
    except Exception as exc:
        print("USER LOGIN EMAIL ERROR:", repr(exc))
    admin_emails = list(User.objects.filter(
        role="admin", is_active=True).values_list("email", flat=True))
    if admin_emails:
        try:
            send_brevo_email(
                to_emails=admin_emails,
                subject="MKCDP - New User Login",
                text_content=(
                    "A user has logged into the MKCDP Child-Tracking-System.\n\n"
                    f"User: {user.email}\nRole: {user.role}\nTime: {login_time}\nDevice: {device_info}\nIP Address: {ip}\n\n"
                    "This is an automated notification."
                ),
                html_content=f"""
                    <div style="font-family:Arial,sans-serif;max-width:600px;margin:40px auto;padding:30px;border:1px solid #e5e5e5;border-radius:12px;">
                        <h2>MKCDP - New User Login</h2>
                        <p>A user has logged into the MKCDP Child-Tracking-System.</p>
                        <p><strong>User:</strong> {user.email}</p>
                        <p><strong>Role:</strong> {user.role}</p>
                        <p><strong>Time:</strong> {login_time}</p>
                        <p><strong>IP Address:</strong> {ip}</p>
                        <p>This is an automated notification.</p>
                    </div>
                """,
            )
        except Exception as exc:
            print("ADMIN LOGIN EMAIL ERROR:", repr(exc))
    profile_picture_url = user.profile_picture.url if user.profile_picture else None
    return {**tokens, "user": {
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "role": user.role,
        "profile_picture": profile_picture_url,
        "dark_mode": user.dark_mode,
        "notifications_enabled": user.notifications_enabled,
    }}


class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data.get("password", "")
        if not password:
            return Response({"detail": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = authenticate(request, email=email, password=password)
        if not user:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response(
                {"detail": "Your account has been deactivated. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if otp_recently_verified(user):
            response_data = create_login_response(user, request)
            response_data["requires_otp"] = False
            response_data["detail"] = "Login successful."
            return Response(response_data, status=status.HTTP_200_OK)
        OTP.objects.filter(user=user, is_used=False).update(is_used=True)
        otp, code = OTP.create_for_user(user)
        try:
            result = send_brevo_email(
                to_emails=email,
                subject="Your MKCDP Child Tracking System login code",
                text_content=f"Here is your one-time login code: {code}. It expires in 10 minutes.",
                html_content=f"""
                    <div style="font-family:Arial,sans-serif;max-width:500px;margin:40px auto;padding:30px;border:1px solid #e5e5e5;border-radius:12px;">
                        <h2>MKCDP Child Tracking System</h2>
                        <p>Your one-time login code is:</p>
                        <div style="font-size:32px;font-weight:bold;letter-spacing:8px;text-align:center;padding:20px;margin:20px 0;background:#f5f5f5;border-radius:10px;">
                            {code}
                        </div>
                        <p>This code expires in 10 minutes.</p>
                        <p>If you did not request this code, you can safely ignore this email.</p>
                    </div>
                """,
            )
            print("BREVO OTP RESPONSE:", result)
        except Exception as exc:
            print("BREVO OTP ERROR:", repr(exc))
            otp.delete()
            return Response(
                {"detail": "The verification email could not be sent. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"requires_otp": True, "detail": "OTP sent to email."}, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "Invalid email or code."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response(
                {"detail": "Your account has been deactivated. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        otp = user.otps.filter(is_used=False).order_by("-created_at").first()
        if not otp:
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)
        if not otp.is_valid():
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_password(code, otp.code_hash):
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        user.last_password_auth = timezone.now()
        user.save(update_fields=["last_password_auth"])
        response_data = create_login_response(user, request)
        response_data["requires_otp"] = False
        return Response(response_data, status=status.HTTP_200_OK)


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
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class LogoutAllDevicesView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        user = request.user
        outstanding = OutstandingToken.objects.filter(user=user)
        for token in outstanding:
            try:
                BlacklistedToken.objects.get_or_create(token=token)
            except Exception:
                pass
        user.last_activity = None
        user.save(update_fields=["last_activity"])
        log_activity(user, 'LOGOUT_ALL', request)
        return Response({"detail": "Logged out from all devices."}, status=status.HTTP_200_OK)


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data.get("role", "employee")
        password = request.data.get("password", "")
        if not password:
            alphabet = string.ascii_letters + string.digits
            generated_password = "".join(
                secrets.choice(alphabet) for _ in range(12))
            user = User.objects.create_user(
                email=serializer.validated_data["email"],
                role=role,
                username=serializer.validated_data.get("username", ""),
                password=generated_password
            )
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
        recent_hashes = UserPasswordHistory.objects.filter(
            user=user_obj)[:PASSWORD_HISTORY_COUNT]
        for entry in recent_hashes:
            if check_password(new_password, entry.password_hash):
                return Response({
                    "detail": f"You cannot reuse your last {PASSWORD_HISTORY_COUNT} passwords."
                }, status=status.HTTP_400_BAD_REQUEST)
        user_obj.set_password(new_password)
        user_obj.save(update_fields=["password"])
        UserPasswordHistory.objects.create(
            user=user_obj, password_hash=make_password(new_password))
        log_activity(request.user, 'RESET_PASSWORD', request,
                     {"target_user": user_obj.email})
        logout_all = request.data.get("logout_all_devices", False)
        if logout_all:
            outstanding = OutstandingToken.objects.filter(user=user_obj)
            for token in outstanding:
                try:
                    BlacklistedToken.objects.get_or_create(token=token)
                except Exception:
                    pass
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
        logs = logs[:500]
        serializer = ActivityLogSerializer(logs, many=True)
        return Response(serializer.data)


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer = UserProfileSerializer(
            user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PublicKeyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = request.data.get("key")

        if not key:
            return Response(
                {"detail": "key is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        public_key, created = PublicKey.objects.update_or_create(
            user=request.user,
            defaults={"key": key}
        )

        return Response(
            {"key": public_key.key},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
