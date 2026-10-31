import os
import secrets
import string
import requests

from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken
)

from .models import (
    OTP,
    UserSession,
    UserPasswordHistory,
    ActivityLog,
    PublicKey
)

from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    CreateUserSerializer,
    UserSerializer,
    UserProfileSerializer,
    UserSessionSerializer,
    ActivityLogSerializer,
    PublicKeySerializer
)

from .permissions import IsAdmin


User = get_user_model()

OTP_INTERVAL_HOURS = 12
PASSWORD_HISTORY_COUNT = 5


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return (
        request.META.get("HTTP_X_REAL_IP")
        or request.META.get("REMOTE_ADDR", "")
    ).strip()


def get_user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")


def log_activity(user, action, request, details=None):
    ActivityLog.objects.create(
        user=user,
        action=action,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        details=details or {}
    )


def send_brevo_email(to_emails, subject, text_content, html_content=None):
    api_key = os.environ.get("BREVO_API_KEY")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL")
    sender_name = os.environ.get(
        "BREVO_SENDER_NAME",
        "MKCDP Child Tracking System"
    )

    if not api_key:
        raise ValueError("BREVO_API_KEY is not configured.")

    if not sender_email:
        raise ValueError("BREVO_SENDER_EMAIL is not configured.")

    if isinstance(to_emails, str):
        to_emails = [to_emails]

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [{"email": email} for email in to_emails],
        "subject": subject,
        "textContent": text_content
    }

    if html_content:
        payload["htmlContent"] = html_content

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        },
        json=payload,
        timeout=10
    )

    response.raise_for_status()
    return response.json()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    refresh["role"] = user.role
    refresh["name"] = user.get_full_name() or user.username
    refresh["email"] = user.email

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token)
    }


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
        user=user,
        action="LOGIN",
        ip_address=ip,
        user_agent=ua
    )

    user.last_ip = ip
    user.last_activity = now
    user.save(update_fields=["last_ip", "last_activity"])

    tokens = get_tokens_for_user(user)

    log_activity(user, "LOGIN", request)

    display_name = (
        user.get_full_name()
        or user.preferred_name
        or user.username
        or user.email
    )

    try:
        send_brevo_email(
            to_emails=user.email,
            subject="MKCDP Login Notification",
            text_content=(
                f"Dear {display_name},\n\n"
                "A login to your MKCDP account was detected.\n\n"
                f"Email: {user.email}\n"
                f"Time: {now.strftime('%d-%m-%Y %H:%M:%S')}\n"
                f"Device: {ua or 'Unknown device'}\n"
                f"IP Address: {ip}\n\n"
                "If this was not you, contact the administrator."
            )
        )
    except Exception as exc:
        print("USER LOGIN EMAIL ERROR:", repr(exc))

    admin_emails = list(
        User.objects.filter(
            role="admin",
            is_active=True
        ).values_list("email", flat=True)
    )

    if admin_emails:
        try:
            send_brevo_email(
                to_emails=admin_emails,
                subject="MKCDP - New User Login",
                text_content=(
                    "A user has logged into the MKCDP system.\n\n"
                    f"User: {display_name}\n"
                    f"Email: {user.email}\n"
                    f"Role: {user.role}\n"
                    f"Time: {now.strftime('%d-%m-%Y %H:%M:%S')}\n"
                    f"IP Address: {ip}"
                )
            )
        except Exception as exc:
            print("ADMIN LOGIN EMAIL ERROR:", repr(exc))

    profile_picture_url = (
        user.profile_picture.url
        if user.profile_picture
        else None
    )

    return {
        **tokens,
        "user": {
            "name": display_name,
            "email": user.email,
            "role": user.role,
            "profile_picture": profile_picture_url,
            "dark_mode": user.dark_mode,
            "notifications_enabled": user.notifications_enabled
        }
    }


class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data.get("password", "")

        if not password:
            return Response(
                {"detail": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(
            request,
            email=email,
            password=password
        )

        if not user:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            return Response(
                {"detail": "Your account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN
            )

        if otp_recently_verified(user):
            data = create_login_response(user, request)
            data["requires_otp"] = False
            data["detail"] = "Login successful."

            return Response(data)

        OTP.objects.filter(
            user=user,
            is_used=False
        ).update(is_used=True)

        otp, code = OTP.create_for_user(user)

        try:
            send_brevo_email(
                to_emails=email,
                subject="Your MKCDP Child Tracking System login code",
                text_content=(
                    f"Your one-time login code is {code}. "
                    "It expires in 10 minutes."
                ),
                html_content=f"""
                    <div style="font-family:Arial,sans-serif;
                    max-width:500px;margin:40px auto;padding:30px;
                    border:1px solid #e5e5e5;border-radius:12px;">
                        <h2>MKCDP Child Tracking System</h2>
                        <p>Your one-time login code is:</p>
                        <div style="font-size:32px;font-weight:bold;
                        letter-spacing:8px;text-align:center;
                        padding:20px;background:#f5f5f5;
                        border-radius:10px;">{code}</div>
                        <p>This code expires in 10 minutes.</p>
                    </div>
                """
            )
        except Exception as exc:
            print("BREVO OTP ERROR:", repr(exc))
            otp.delete()

            return Response(
                {"detail": "The verification email could not be sent."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response({
            "requires_otp": True,
            "detail": "OTP sent to email."
        })


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
            return Response(
                {"detail": "Invalid email or code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            return Response(
                {"detail": "Your account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN
            )

        otp = user.otps.filter(
            is_used=False
        ).order_by("-created_at").first()

        if not otp or not otp.is_valid():
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not check_password(code, otp.code_hash):
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        user.last_password_auth = timezone.now()
        user.save(update_fields=["last_password_auth"])

        data = create_login_response(user, request)
        data["requires_otp"] = False

        return Response(data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        UserSession.objects.create(
            user=request.user,
            action="LOGOUT",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )

        request.user.last_activity = None
        request.user.save(update_fields=["last_activity"])

        log_activity(request.user, "LOGOUT", request)

        try:
            refresh_token = request.data.get("refresh")

            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            pass

        return Response({"detail": "Logged out successfully."})


class LogoutAllDevicesView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        outstanding = OutstandingToken.objects.filter(
            user=request.user
        )

        for token in outstanding:
            BlacklistedToken.objects.get_or_create(token=token)

        request.user.last_activity = None
        request.user.save(update_fields=["last_activity"])

        log_activity(request.user, "LOGOUT", request, {
            "action": "logout_all_devices"
        })

        return Response({
            "detail": "Logged out from all devices."
        })


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        password = serializer.validated_data.get("password")
        generated = not bool(password)

        if generated:
            alphabet = string.ascii_letters + string.digits
            password = "".join(
                secrets.choice(alphabet)
                for _ in range(12)
            )

        try:
            user = serializer.save(password=password)
        except IntegrityError:
            return Response(
                {"detail": "An employee with these details already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        UserPasswordHistory.objects.create(
            user=user,
            password_hash=make_password(password)
        )

        log_activity(
            request.user,
            "CREATE_USER",
            request,
            {
                "created_user": user.email,
                "generated": generated
            }
        )

        data = UserSerializer(user).data

        if generated:
            data["generated_password"] = password

        return Response(data, status=status.HTTP_201_CREATED)


class ListUsersView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.all().order_by("email")

        serializer = UserSerializer(users, many=True)

        return Response(serializer.data)


class UpdateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        try:
            employee = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "Employee not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CreateUserSerializer(
            employee,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        try:
            employee = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "The employee number or email is already in use."},
                status=status.HTTP_400_BAD_REQUEST
            )

        log_activity(
            request.user,
            "UPDATE_USER",
            request,
            {"updated_user": employee.email}
        )

        return Response(UserSerializer(employee).data)


class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, pk):
        try:
            employee = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if employee == request.user:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = employee.email
        employee.delete()

        log_activity(
            request.user,
            "DELETE_USER",
            request,
            {"deleted_user": email}
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateUserStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        try:
            employee = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if employee == request.user:
            return Response(
                {"detail": "You cannot change your own status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if "is_active" not in request.data:
            return Response(
                {"detail": "is_active field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_active = request.data["is_active"]

        if isinstance(is_active, str):
            is_active = is_active.lower() == "true"

        employee.is_active = bool(is_active)
        employee.save(update_fields=["is_active"])

        log_activity(
            request.user,
            "UPDATE_USER_STATUS",
            request,
            {
                "user": employee.email,
                "new_status": employee.is_active
            }
        )

        return Response(UserSerializer(employee).data)


class UserSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        email = request.query_params.get("email", "").strip()

        if not email:
            return Response(
                {"detail": "Email query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            employee = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        sessions = UserSession.objects.filter(
            user=employee
        ).select_related("user")

        return Response(
            UserSessionSerializer(sessions, many=True).data
        )


class CheckActiveStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "is_active": request.user.is_active,
            "email": request.user.email
        })


class ResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            employee = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        new_password = request.data.get("password", "")

        if not new_password:
            alphabet = string.ascii_letters + string.digits
            new_password = "".join(
                secrets.choice(alphabet)
                for _ in range(12)
            )

        recent_hashes = UserPasswordHistory.objects.filter(
            user=employee
        )[:PASSWORD_HISTORY_COUNT]

        for entry in recent_hashes:
            if check_password(new_password, entry.password_hash):
                return Response(
                    {
                        "detail": (
                            f"You cannot reuse your last "
                            f"{PASSWORD_HISTORY_COUNT} passwords."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        employee.set_password(new_password)
        employee.save(update_fields=["password"])

        UserPasswordHistory.objects.create(
            user=employee,
            password_hash=make_password(new_password)
        )

        logout_all = request.data.get("logout_all_devices", False)

        if logout_all:
            outstanding = OutstandingToken.objects.filter(
                user=employee
            )

            for token in outstanding:
                BlacklistedToken.objects.get_or_create(token=token)

            employee.last_activity = None
            employee.save(update_fields=["last_activity"])

        log_activity(
            request.user,
            "RESET_PASSWORD",
            request,
            {"target_user": employee.email}
        )

        return Response({
            "email": employee.email,
            "new_password": new_password,
            "logout_all_devices": logout_all
        })


class ActivityLogListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        email = request.query_params.get("email")

        logs = ActivityLog.objects.all()

        if email:
            try:
                employee = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            logs = logs.filter(user=employee)

        logs = logs.select_related("user").order_by("-timestamp")[:500]

        return Response(
            ActivityLogSerializer(logs, many=True).data
        )


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )

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
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            )
        )

    def get(self, request, email=None):
        if email:
            try:
                employee = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            try:
                return Response({"key": employee.public_key.key})
            except PublicKey.DoesNotExist:
                return Response(
                    {"detail": "Recipient has no public key."},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            return Response({"key": request.user.public_key.key})
        except PublicKey.DoesNotExist:
            return Response({"key": None})