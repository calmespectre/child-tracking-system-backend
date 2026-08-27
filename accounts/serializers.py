from rest_framework import serializers
from .models import User, UserSession, ActivityLog, PublicKey, ChatMessage


class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if not User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "No account found with this email.")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(
        required=False, allow_blank=True, default="")

    class Meta:
        model = User
        fields = ["email", "role", "username", "password"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        username = validated_data.pop("username", "")
        if not username:
            username = validated_data.get("email")
        validated_data["username"] = username
        return User.objects.create_user(password=password, **validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role", "is_active"]


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "role", "profile_picture"]
        read_only_fields = ["id", "email", "role"]


class UserSessionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = UserSession
        fields = ["id", "user", "user_email", "action",
                  "ip_address", "user_agent", "timestamp"]
        read_only_fields = ["id", "user", "user_email",
                            "action", "ip_address", "user_agent", "timestamp"]


class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ActivityLog
        fields = ["id", "user", "user_email", "action",
                  "ip_address", "user_agent", "details", "timestamp"]
        read_only_fields = ["id", "user", "user_email", "action",
                            "ip_address", "user_agent", "details", "timestamp"]


class PublicKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicKey
        fields = ["id", "user", "key", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(
        source="sender.email", read_only=True)
    sender_name = serializers.CharField(
        source="sender.username", read_only=True)
    recipient_email = serializers.EmailField(
        source="recipient.email", read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "sender_email", "sender_name", "recipient",
                  "recipient_email", "message", "attachment", "attachment_type", "timestamp", "is_read"]
        read_only_fields = ["id", "sender", "timestamp", "is_read"]
