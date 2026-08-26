from django.db import models
from django.conf import settings


class Beneficiary(models.Model):
    GENDER_CHOICES = [
        ('Female', 'Female'),
        ('Male', 'Male'),
    ]
    SPONSORSHIP_STATUS_CHOICES = [
        ('Sponsored', 'Sponsored'),
        ('Pre-Sponsored', 'Pre-Sponsored'),
        ('Enrolled', 'Enrolled'),
        ('Reinstateable', 'Reinstateable'),
        ('Available', 'Available'),
        ('Reserved', 'Reserved'),
        ('Check Materials', 'Check Materials'),
        ('Unavailable', 'Unavailable'),
    ]

    community_number = models.CharField(max_length=50, blank=True, default='')
    last_name = models.CharField(max_length=255)
    child_number = models.CharField(max_length=50, unique=True)
    participant_case_number = models.CharField(
        max_length=50, blank=True, default='')
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES, default='Female')
    short_name = models.CharField(max_length=100, blank=True, default='')
    birthdate = models.DateField(null=True, blank=True)
    sponsorship_status = models.CharField(
        max_length=30, choices=SPONSORSHIP_STATUS_CHOICES, default='Sponsored')
    enrollment_date = models.DateField(null=True, blank=True)
    narrative_date = models.DateField(null=True, blank=True)
    photo_date = models.DateField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    village = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['child_number']),
            models.Index(fields=['last_name']),
            models.Index(fields=['village']),
        ]

    def __str__(self):
        return f"{self.child_number} - {self.last_name}"


class Guardian(models.Model):
    beneficiary = models.ForeignKey(
        Beneficiary, on_delete=models.CASCADE, related_name='guardians')
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    id_number = models.CharField(max_length=50, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.relationship})"


class Document(models.Model):
    beneficiary = models.ForeignKey(
        Beneficiary, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    type = models.CharField(max_length=100, blank=True, default='')
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Note(models.Model):
    beneficiary = models.ForeignKey(
        Beneficiary, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note by {self.author} on {self.date}"
