from django.db import models
from django.conf import settings


class Beneficiary(models.Model):
    GENDER_CHOICES = [
        ("Female", "Female"),
        ("Male", "Male"),
    ]

    STATUS_CHOICES = [
        ("Sponsored", "Sponsored"),
        ("Pre-Sponsored", "Pre-Sponsored"),
        ("Enrolled", "Enrolled"),
        ("Reinstateable", "Reinstateable"),
        ("Available", "Available"),
        ("Reserved", "Reserved"),
        ("Check Materials", "Check Materials"),
        ("Unavailable", "Unavailable"),
    ]

    community_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
    )

    last_name = models.CharField(
        max_length=150,
        db_index=True,
    )

    child_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    participant_case_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default="Female",
    )

    short_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )

    birthdate = models.DateField(
        null=True,
        blank=True,
    )

    age = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    village = models.CharField(
        max_length=150,
        blank=True,
        default="",
        db_index=True,
    )

    sponsorship_status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Sponsored",
        db_index=True,
    )

    enrollment_date = models.DateField(
        null=True,
        blank=True,
    )

    narrative_date = models.DateField(
        null=True,
        blank=True,
    )

    photo_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_beneficiaries",
    )

    class Meta:
        ordering = ["-child_number"]

        indexes = [
            models.Index(fields=["last_name"]),
            models.Index(fields=["child_number"]),
            models.Index(fields=["short_name"]),
            models.Index(fields=["village"]),
            models.Index(fields=["community_number"]),
            models.Index(fields=["sponsorship_status"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["-child_number"]),
        ]

    def __str__(self):
        return f"{self.last_name} ({self.child_number})"


class Note(models.Model):
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name="notes",
    )

    author = models.CharField(
        max_length=100,
        default="You",
    )

    date = models.DateField(
        auto_now_add=True,
    )

    text = models.TextField()

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Note for {self.beneficiary}"


class Document(models.Model):
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    file = models.FileField(
        upload_to="beneficiary_docs/",
    )

    name = models.CharField(
        max_length=255,
    )

    size = models.PositiveIntegerField(
        default=0,
    )

    type = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.name


class SupportLog(models.Model):
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name="support_logs",
    )

    type = models.CharField(
        max_length=50,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    date = models.DateField()

    notes = models.TextField(
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        default="Pending",
        db_index=True,
    )

    approved_by = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    status_updated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    logged_at = models.DateTimeField(
        auto_now_add=True,
    )

    logged_by = models.EmailField(
        blank=True,
        default="",
    )

    class Meta:
        ordering = ["-logged_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["date"]),
            models.Index(fields=["beneficiary", "status"]),
        ]

    def __str__(self):
        return f"{self.type} - {self.beneficiary}"
