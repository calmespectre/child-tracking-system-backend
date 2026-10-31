from datetime import timedelta
import random

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field is required")

        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EMPLOYEE = "employee", "Employee"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERN = "intern", "Intern"
        VOLUNTEER = "volunteer", "Volunteer"
        TEMPORARY = "temporary", "Temporary"

    class EmploymentStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On leave"
        SUSPENDED = "suspended", "Suspended"
        TERMINATED = "terminated", "Terminated"
        RESIGNED = "resigned", "Resigned"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE
    )

    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(
        upload_to="profile_pics/",
        null=True,
        blank=True
    )

    first_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    preferred_name = models.CharField(max_length=150, blank=True)

    gender = models.CharField(
        max_length=30,
        choices=Gender.choices,
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    national_id = models.CharField(max_length=100, blank=True)
    passport_number = models.CharField(max_length=100, blank=True)

    personal_email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    alternative_phone = models.CharField(max_length=30, blank=True)
    residential_address = models.TextField(blank=True)
    town = models.CharField(max_length=150, blank=True)
    county = models.CharField(max_length=150, blank=True)

    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_alternative_phone = models.CharField(max_length=30, blank=True)

    employee_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )
    job_title = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=150, blank=True)
    employment_type = models.CharField(
        max_length=30,
        choices=EmploymentType.choices,
        blank=True
    )
    employment_status = models.CharField(
        max_length=30,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE
    )
    employment_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    reporting_manager = models.CharField(max_length=200, blank=True)
    work_location = models.CharField(max_length=200, blank=True)
    responsibilities = models.TextField(blank=True)

    last_password_auth = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)

    dark_mode = models.BooleanField(default=False)
    notifications_enabled = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def full_name(self):
        return " ".join(
            part for part in [
                self.first_name,
                self.middle_name,
                self.last_name
            ] if part
        )


class OTP(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otps"
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    @staticmethod
    def generate_code():
        return f"{random.randint(0, 999999):06d}"

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    def create_for_user(cls, user, lifetime_minutes=10):
        from django.contrib.auth.hashers import make_password

        code = cls.generate_code()
        otp = cls.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=timezone.now() + timedelta(minutes=lifetime_minutes)
        )
        return otp, code


class UserSession(models.Model):
    ACTION_CHOICES = [
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions"
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.email} - {self.action} at {self.timestamp}"


class UserPasswordHistory(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_history"
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("CREATE_USER", "Create User"),
        ("UPDATE_USER", "Update User"),
        ("DELETE_USER", "Delete User"),
        ("UPDATE_USER_STATUS", "Update User Status"),
        ("RESET_PASSWORD", "Reset Password"),
        ("PASSWORD_CHANGE", "Password Change"),
        ("ADD_BENEFICIARY", "Add Beneficiary"),
        ("EDIT_BENEFICIARY", "Edit Beneficiary"),
        ("DELETE_BENEFICIARY", "Delete Beneficiary"),
        ("ADD_DISBURSEMENT", "Add Disbursement"),
        ("EDIT_DISBURSEMENT", "Edit Disbursement"),
        ("DELETE_DISBURSEMENT", "Delete Disbursement"),
        ("BULK_IMPORT_BENEFICIARIES", "Bulk Import Beneficiaries"),
        ("BULK_IMPORT_DISBURSEMENTS", "Bulk Import Disbursements"),
        ("IMPORT_GUARDIANS", "Import Guardians"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs"
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]


class PublicKey(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="public_key"
    )
    key = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)