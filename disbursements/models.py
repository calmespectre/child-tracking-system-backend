from django.conf import settings
from django.db import models


class Bursary(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Disbursed", "Disbursed"),
        ("Rejected", "Rejected"),
    ]

    zone = models.CharField(max_length=150, blank=True, default="")
    case_number = models.CharField(max_length=150, blank=True, default="")
    admission_number = models.CharField(max_length=150, blank=True, default="")
    beneficiary_name = models.CharField(max_length=255)
    school = models.CharField(max_length=255, blank=True, default="")
    grade = models.CharField(max_length=100, blank=True, default="")
    performance = models.CharField(max_length=255, blank=True, default="")
    account_number = models.CharField(max_length=150, blank=True, default="")
    branch = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Pending"
    )
    notes = models.TextField(blank=True, default="")
    beneficiary = models.ForeignKey(
        "beneficiaries.Beneficiary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bursaries"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bursaries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["zone"]),
            models.Index(fields=["case_number"]),
            models.Index(fields=["admission_number"]),
            models.Index(fields=["beneficiary_name"]),
            models.Index(fields=["school"]),
            models.Index(fields=["grade"]),
            models.Index(fields=["account_number"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["status"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.beneficiary_name} - {self.school} - {self.amount}"