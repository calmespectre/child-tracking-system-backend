from rest_framework import serializers

from .models import (
    User,
    UserSession,
    ActivityLog,
    PublicKey
)


EMPLOYEE_FIELDS = [
    "id",
    "email",
    "username",
    "role",
    "first_name",
    "middle_name",
    "last_name",
    "preferred_name",
    "gender",
    "date_of_birth",
    "nationality",
    "national_id",
    "passport_number",
    "personal_email",
    "phone_number",
    "alternative_phone",
    "residential_address",
    "town",
    "county",
    "emergency_contact_name",
    "emergency_contact_relationship",
    "emergency_contact_phone",
    "emergency_contact_alternative_phone",
    "employee_number",
    "job_title",
    "department",
    "employment_type",
    "employment_status",
    "employment_start_date",
    "contract_end_date",
    "reporting_manager",
    "work_location",
    "responsibilities",
    "is_active",
    "date_joined",
    "last_login",
]


class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if not User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "No account found with this email."
            )
        return value


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    username = serializers.CharField(
        required=False,
        allow_blank=True
    )

    class Meta:
        model = User
        fields = EMPLOYEE_FIELDS + ["password"]
        read_only_fields = [
            "id",
            "date_joined",
            "last_login",
        ]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate_employee_number(self, value):
        if not value:
            return None

        queryset = User.objects.filter(employee_number=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "This employee number is already in use."
            )

        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        validated_data["username"] = (
            validated_data.get("username") or validated_data["email"]
        )

        return User.objects.create_user(
            password=password,
            **validated_data
        )


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    profile_picture = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = EMPLOYEE_FIELDS + [
            "name",
            "profile_picture",
            "last_activity",
            "last_ip",
        ]

    def get_name(self, obj):
        return (
            obj.get_full_name()
            or obj.preferred_name
            or obj.username
            or obj.email
        )


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
        except PublicKey.DoesNotExist:
            return None


class UserSessionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True
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
        read_only_fields = fields


class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "user_email",
            "action",
            "ip_address",
            "user_agent",
            "details",
            "timestamp",
        ]
        read_only_fields = fields


class PublicKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicKey
        fields = [
            "id",
            "user",
            "key",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]