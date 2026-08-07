from django.contrib.auth import get_user_model, authenticate
from django.core.mail import send_mail
from django.contrib.auth.hashers import check_password
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
import secrets
import string
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


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["name"] = user.get_full_name() or user.username
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def get_client_ip(request):
    # Try common proxy headers
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the list (the original client IP)
        ip = x_forwarded_for.split(',')[0].strip()
        return ip
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    return request.META.get('REMOTE_ADDR', '')


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

        otp, code = OTP.create_for_user(user)
        send_mail(
            subject="Your MkCDP Child Tracking System login code",
            message=f"Here’s your one-time login code: {code}. It expires in 10 minutes.",
            from_email=None,
            recipient_list=[email],
        )
        return Response({"detail": "OTP sent to email."}, status=status.HTTP_200_OK)


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
            return Response({"detail": "Invalid email or code."}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_active:
            return Response(
                {"detail": "Your account has been deactivated. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        otp = user.otps.filter(is_used=False).order_by("-created_at").first()
        if not otp or not otp.is_valid() or not check_password(code, otp.code_hash):
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

        otp.is_used = True
        otp.save()

        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        UserSession.objects.create(
            user=user, action="LOGIN", ip_address=ip, user_agent=ua)

        user.last_ip = ip
        user.last_activity = timezone.now()
        user.save(update_fields=["last_ip", "last_activity"])

        tokens = get_tokens_for_user(user)

        login_time = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
        device_info = ua or "Unknown device"

        send_mail(
            subject="MkCDP Login Notification",
            message=(
                f"Dear {user.get_full_name() or user.username},\n\n"
                f"A login to your MKCDP Child-Tracking-System account was detected.\n\n"
                f"Email: {user.email}\n"
                f"Time: {login_time}\n"
                f"Device: {device_info}\n"
                f"IP Address: {ip}\n\n"
                f"If this was not you, please contact the administrator immediately."
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

        admin_emails = list(User.objects.filter(
            role="admin", is_active=True).values_list("email", flat=True))
        if admin_emails:
            send_mail(
                subject="MkCDP – New User Login",
                message=(
                    f"A user has logged into the MKCDP system Child-Tracking-System.\n\n"
                    f"User: {user.email}\n"
                    f"Role: {user.role}\n"
                    f"Time: {login_time}\n"
                    f"Device: {device_info}\n"
                    f"IP Address: {ip}\n\n"
                    f"This is an automated notification."
                ),
                from_email=None,
                recipient_list=admin_emails,
                fail_silently=True,
            )

        return Response({
            **tokens,
            "user": {
                "name": user.get_full_name() or user.username,
                "email": user.email,
                "role": user.role,
            },
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        UserSession.objects.create(
            user=request.user, action="LOGOUT", ip_address=ip, user_agent=ua)
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "id": user.id,
            "email": user.email,
            "role": user.role,
        }, status=status.HTTP_201_CREATED)


class ListUsersView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if user_obj == request.user:
            return Response({"detail": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST)
        user_obj.delete()
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

        is_active = request.data.get("is_active")
        if is_active is None:
            return Response({"detail": "is_active field is required."}, status=status.HTTP_400_BAD_REQUEST)

        user_obj.is_active = bool(is_active)
        user_obj.save()
        serializer = UserSerializer(user_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        email = request.query_params.get("email")
        if not email:
            return Response({"detail": "Email query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        sessions = user_obj.sessions.all()
        serializer = UserSessionSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CheckActiveStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "is_active": request.user.is_active,
            "email": request.user.email,
        }, status=status.HTTP_200_OK)


class ResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user_obj = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user_obj.set_password(new_password)
        user_obj.save()

        return Response({
            "email": user_obj.email,
            "new_password": new_password,
        }, status=status.HTTP_200_OK)
