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

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', null=True, blank=True)
    last_password_auth = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"


class OTP(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="otps")
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
            expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
        )
        return otp, code


class UserSession(models.Model):
    ACTION_CHOICES = [
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
    ]
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sessions")
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
        User, on_delete=models.CASCADE, related_name="password_history")
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('CREATE_USER', 'Create User'),
        ('DELETE_USER', 'Delete User'),
        ('UPDATE_USER_STATUS', 'Update User Status'),
        ('RESET_PASSWORD', 'Reset Password'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('ADD_BENEFICIARY', 'Add Beneficiary'),
        ('EDIT_BENEFICIARY', 'Edit Beneficiary'),
        ('DELETE_BENEFICIARY', 'Delete Beneficiary'),
        ('ADD_DISBURSEMENT', 'Add Disbursement'),
        ('EDIT_DISBURSEMENT', 'Edit Disbursement'),
        ('DELETE_DISBURSEMENT', 'Delete Disbursement'),
        ('BULK_IMPORT_BENEFICIARIES', 'Bulk Import Beneficiaries'),
        ('BULK_IMPORT_DISBURSEMENTS', 'Bulk Import Disbursements'),
        ('IMPORT_GUARDIANS', 'Import Guardians'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="activity_logs")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]


class PublicKey(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='public_key')
    key = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ChatMessage(models.Model):
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received_messages')
    encrypted_message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
