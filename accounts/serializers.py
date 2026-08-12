from rest_framework import serializers

from .models import User, UserSession


class RequestOTPSerializer(
    serializers.Serializer
):
    email = serializers.EmailField()

    password = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate_email(self, value):
        if not User.objects.filter(
            email__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "No account found with this email."
            )

        return value


class VerifyOTPSerializer(
    serializers.Serializer
):
    email = serializers.EmailField()

    code = serializers.CharField(
        max_length=6,
        min_length=6,
    )


class CreateUserSerializer(
    serializers.ModelSerializer
):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    username = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    class Meta:
        model = User

        fields = [
            "email",
            "role",
            "username",
            "password",
        ]

    def validate_email(self, value):
        if User.objects.filter(
            email__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

    def create(self, validated_data):
        password = validated_data.pop(
            "password",
            None,
        )

        username = validated_data.pop(
            "username",
            "",
        )

        if not username:
            username = validated_data.get(
                "email"
            )

        validated_data["username"] = (
            username
        )

        return User.objects.create_user(
            password=password,
            **validated_data,
        )


class UserSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = User

        fields = [
            "id",
            "email",
            "role",
            "is_active",
        ]


class UserSessionSerializer(
    serializers.ModelSerializer
):
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    class Meta:
        model = UserSession

        fields = [
            "id",
            "user",
            "user_email",
            "action",
            "ip_address",
            "user_agent",
            "timestamp",
        ]

        read_only_fields = [
            "id",
            "user",
            "user_email",
            "action",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
