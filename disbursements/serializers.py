from rest_framework import serializers
from .models import Bursary


class BursarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Bursary
        fields = [
            "id",
            "zone",
            "case_number",
            "admission_number",
            "beneficiary_name",
            "school",
            "grade",
            "performance",
            "account_number",
            "branch",
            "amount",
            "date",
            "status",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
        ]
