from django.db import models
from django.conf import settings


class Disbursement(models.Model):
    PROGRAM_CHOICES = [
        ('bursaries', 'Bursaries'),
        ('scholarships', 'Scholarship'),
        ('child-friendly-desks', 'Provision of Child Friendly Desks'),
        ('school-infrastructure', 'Improvement of School Infrastructure'),
        ('asali-tamu', 'Asali Tamu Initiative'),
        ('sahiwal-heifers', 'Provision of Sahiwal Heifers'),
        ('galla-goats', 'Provision of Galla Goats'),
        ('kienyeji-chicks', 'Provision of Improved Kienyeji Chicks'),
        ('vsla-tents-chairs', 'Provision of Tents & Chairs to VSLA Groups'),
        ('moilo-water-project', 'Development of Moilo Water Project'),
        ('olkina-water-project', 'Development of Olkina Water Project'),
        ('lenkisim-water-project', 'Development of Lenkisim Water Project'),
        ('nataana-water-project', 'Rehabilitation of Nataana Water Project'),
        ('water-tanks-gutters', 'Provision of Water Tanks & Installation of Gutters'),
        ('drought-tolerant-seeds', 'Provision of Drought Tolerant Seeds'),
        ('aflatoun-4k-clubs', 'Establishment Aflatoun 4K Clubs'),
        ('school-feeding', 'School Feeding Programs'),
    ]
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Disbursed", "Disbursed"),
        ("Rejected", "Rejected"),
    ]
    program = models.CharField(max_length=50, choices=PROGRAM_CHOICES)
    zone = models.CharField(max_length=150, blank=True, default="")
    case_number = models.CharField(max_length=150, blank=True, default="")
    admission_number = models.CharField(max_length=150, blank=True, default="")
    beneficiary_name = models.CharField(max_length=255, blank=True, default="")
    school = models.CharField(max_length=255, blank=True, default="")
    grade = models.CharField(max_length=100, blank=True, default="")
    performance = models.CharField(max_length=255, blank=True, default="")
    account_number = models.CharField(max_length=150, blank=True, default="")
    branch = models.CharField(max_length=255, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    quantity = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Pending")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_disbursements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["program"]),
            models.Index(fields=["zone"]),
            models.Index(fields=["case_number"]),
            models.Index(fields=["admission_number"]),
            models.Index(fields=["beneficiary_name"]),
            models.Index(fields=["school"]),
            models.Index(fields=["account_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.beneficiary_name} - {self.program} ({self.status})"
