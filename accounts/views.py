import os
import secrets
import string
import requests

from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTP, UserSession
from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    CreateUserSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from .permissions import IsAdmin

User = get_user_model()


def send_brevo_email(to_emails, subject, text_content, html_content=None):
    api_key = os.environ.get("BREVO_API_KEY")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL")
    sender_name = os.environ.get(
        "BREVO_SENDER_NAME",
        "MKCDP Child Tracking System",
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
            "email": sender_email,
        },
        "to": [
            {"email": email}
            for email in to_emails
        ],
        "subject": subject,
        "textContent": text_content,
    }

    if html_content:
        payload["htmlContent"] = html_content

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json=payload,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.META.get("HTTP_X_REAL_IP")

    if x_real_ip:
        return x_real_ip.strip()

    return request.META.get("REMOTE_ADDR", "").strip()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    refresh["role"] = user.role
    refresh["name"] = user.get_full_name() or user.username

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
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
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            email=email,
            password=password,
        )

        if not user:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {
                    "detail": "Your account has been deactivated. Please contact the administrator."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        otp, code = OTP.create_for_user(user)

        try:
            result = send_brevo_email(
                to_emails=email,
                subject="Your MKCDP Child Tracking System login code",
                text_content=(
                    f"Here is your one-time login code: {code}. "
                    "It expires in 10 minutes."
                ),
                html_content=f"""
                    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 40px auto; padding: 30px; border: 1px solid #e5e5e5; border-radius: 12px;">
                        <h2>MKCDP Child Tracking System</h2>
                        <p>Your one-time login code is:</p>

                        <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; text-align: center; padding: 20px; margin: 20px 0; background: #f5f5f5; border-radius: 10px;">
                            {code}
                        </div>

                        <p>This code expires in 10 minutes.</p>

                        <p>
                            If you did not request this code,
                            you can safely ignore this email.
                        </p>
                    </div>
                """,
            )

            print("BREVO OTP RESPONSE:", result)

        except Exception as exc:
            print("BREVO OTP ERROR:", repr(exc))

            return Response(
                {
                    "detail": "The verification email could not be sent. Please try again."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "detail": "OTP sent to email."
            },
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {
                    "detail": "Your account has been deactivated. Please contact the administrator."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        otp = (
            user.otps
            .filter(is_used=False)
            .order_by("-created_at")
            .first()
        )

        if not otp or not otp.is_valid() or not check_password(code, otp.code_hash):
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.is_used = True
        otp.save()

        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        UserSession.objects.create(
            user=user,
            action="LOGIN",
            ip_address=ip,
            user_agent=ua,
        )

        user.last_ip = ip
        user.last_activity = timezone.now()
        user.save(update_fields=["last_ip", "last_activity"])

        tokens = get_tokens_for_user(user)

        login_time = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
        device_info = ua or "Unknown device"

        try:
            send_brevo_email(
                to_emails=user.email,
                subject="MkCDP Login Notification",
                text_content=(
                    f"Dear {user.get_full_name() or user.username},\n\n"
                    "A login to your MKCDP Child-Tracking-System account was detected.\n\n"
                    f"Email: {user.email}\n"
                    f"Time: {login_time}\n"
                    f"Device: {device_info}\n"
                    f"IP Address: {ip}\n\n"
                    "If this was not you, please contact the administrator immediately."
                ),
                html_content=f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 30px; border: 1px solid #e5e5e5; border-radius: 12px;">
                        <h2>MKCDP Login Notification</h2>
                        <p>Dear {user.get_full_name() or user.username},</p>
                        <p>A login to your MKCDP Child-Tracking-System account was detected.</p>
                        <p><strong>Email:</strong> {user.email}</p>
                        <p><strong>Time:</strong> {login_time}</p>
                        <p><strong>Device:</strong> {device_info}</p>
                        <p><strong>IP Address:</strong> {ip}</p>
                        <p>If this was not you, please contact the administrator immediately.</p>
                    </div>
                """,
            )
        except Exception:
            pass

        admin_emails = list(
            User.objects.filter(
                role="admin",
                is_active=True,
            ).values_list("email", flat=True)
        )

        if admin_emails:
            try:
                send_brevo_email(
                    to_emails=admin_emails,
                    subject="MkCDP - New User Login",
                    text_content=(
                        "A user has logged into the MKCDP system Child-Tracking-System.\n\n"
                        f"User: {user.email}\n"
                        f"Role: {user.role}\n"
                        f"Time: {login_time}\n"
                        f"Device: {device_info}\n"
                        f"IP Address: {ip}\n\n"
                        "This is an automated notification."
                    ),
                    html_content=f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 30px; border: 1px solid #e5e5e5; border-radius: 12px;">
                            <h2>MKCDP - New User Login</h2>
                            <p>A user has logged into the MKCDP Child-Tracking-System.</p>
                            <p><strong>User:</strong> {user.email}</p>
                            <p><strong>Role:</strong> {user.role}</p>
                            <p><strong>Time:</strong> {login_time}</p>
                            <p><strong>Device:</strong> {device_info}</p>
                            <p><strong>IP Address:</strong> {ip}</p>
                            <p>This is an automated notification.</p>
                        </div>
                    """,
                )
            except Exception:
                pass

        return Response(
            {
                **tokens,
                "user": {
                    "name": user.get_full_name() or user.username,
                    "email": user.email,
                    "role": user.role,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        UserSession.objects.create(
            user=request.user,
            action="LOGOUT",
            ip_address=ip,
            user_agent=ua,
        )

        return Response(
            {"detail": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )


class ListUsersView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user_obj == request.user:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_obj.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class UpdateUserStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user_obj == request.user:
            return Response(
                {"detail": "You cannot change your own status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_active = request.data.get("is_active")

        if is_active is None:
            return Response(
                {"detail": "is_active field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_obj.is_active = bool(is_active)
        user_obj.save()

        serializer = UserSerializer(user_obj)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class UserSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        email = request.query_params.get("email", "").strip()

        if not email:
            return Response(
                {"detail": "Email query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_obj = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            sessions = (
                UserSession.objects
                .filter(user=user_obj)
                .select_related("user")
                .order_by("-timestamp")
            )

            serializer = UserSessionSerializer(
                sessions,
                many=True,
            )

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            print("USER SESSION ERROR:", repr(exc))

            return Response(
                {
                    "detail": "Unable to load user sessions.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CheckActiveStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "is_active": request.user.is_active,
                "email": request.user.email,
            },
            status=status.HTTP_200_OK,
        )


class ResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        alphabet = string.ascii_letters + string.digits

        new_password = "".join(
            secrets.choice(alphabet)
            for _ in range(12)
        )

        user_obj.set_password(new_password)
        user_obj.save()

        return Response(
            {
                "email": user_obj.email,
                "new_password": new_password,
            },
            status=status.HTTP_200_OK,
        )
