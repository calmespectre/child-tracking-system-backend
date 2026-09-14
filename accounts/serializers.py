from rest_framework import serializers
from .models import User, UserSession, ActivityLog, PublicKey


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
    name = serializers.CharField(
        required=False, allow_blank=True, write_only=True)
    username = serializers.CharField(
        required=False, allow_blank=True, default="")

    class Meta:
        model = User
        fields = ["email", "role", "name", "username", "password"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        name = validated_data.pop("name", "") or ""
        username = validated_data.pop("username", "")
        if not username:
            username = validated_data.get("email")
        validated_data["username"] = username
        name = name.strip()
        if name:
            parts = name.split(" ", 1)
            validated_data["first_name"] = parts[0]
            validated_data["last_name"] = parts[1] if len(parts) > 1 else ""
        return User.objects.create_user(password=password, **validated_data)


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "is_active"]

    def get_name(self, obj):
        return obj.get_full_name() or obj.username or obj.email


class UserProfileSerializer(serializers.ModelSerializer):
    public_key = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "role",
            "profile_picture",
            "dark_mode",
            "notifications_enabled",
            "public_key",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "public_key",
        ]

    def get_public_key(self, obj):
        try:
            return obj.public_key.key
        except Exception:
            return None


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
